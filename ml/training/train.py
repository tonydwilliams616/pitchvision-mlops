"""PitchVision detector training: fine-tune RT-DETRv2 on the football dataset.

1. Download a versioned dataset (COCO JSON + manifest) from S3
2. Fine-tune a Hugging Face RT-DETRv2 checkpoint (baked into the image)
3. Evaluate on valid (during training) and test (at the end), per class
4. Log params, metrics, dataset manifest, environment and model to MLflow
5. With --register: register a model version and move the "champion" alias
   only if it beats the current champion on test mAP (else "challenger")

Environment: MLFLOW_TRACKING_URI, AWS credentials (Pod Identity), IMAGE_GIT_SHA.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import boto3
import mlflow
import numpy as np
import torch
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchmetrics.detection import MeanAveragePrecision
from transformers import AutoImageProcessor, AutoModelForObjectDetection

MODEL_NAME = "pitchvision-detector"
PRIMARY_METRIC = "test_map"  # COCO mAP@[.50:.95] on the held-out test split
SPLITS = ("train", "valid", "test")
ANNOTATIONS = "_annotations.coco.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset-uri", required=True, help="s3://bucket/dataset/version")
    p.add_argument("--data-dir", default="/tmp/data", help="Local download directory")
    p.add_argument("--checkpoint", default="PekingU/rtdetr_v2_r18vd")
    p.add_argument("--image-size", type=int, default=640, help="Square training resolution")
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--eval-every", type=int, default=5, help="Evaluate on valid every N epochs")
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-images", type=int, default=None, help="Cap images per split (smoke tests)")
    p.add_argument("--no-amp", action="store_true", help="Disable mixed precision on GPU")
    p.add_argument("--experiment", default="pitchvision-detector")
    p.add_argument("--run-name", default=None)
    p.add_argument("--register", action="store_true", help="Register the model and update aliases")
    return p.parse_args()


# --------------------------------------------------------------------------- data
def download_dataset(uri: str, dest: Path) -> Path:
    bucket, _, prefix = uri.removeprefix("s3://").partition("/")
    prefix = prefix.rstrip("/") + "/"
    s3 = boto3.client("s3")
    downloaded = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            target = dest / obj["Key"][len(prefix):]
            if target.exists() and target.stat().st_size == obj["Size"]:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, obj["Key"], str(target))
            downloaded += 1
    print(f"Dataset: {downloaded} files downloaded from {uri} to {dest}")
    return dest


def load_label_map(split_dir: Path) -> tuple[dict[int, int], dict[int, str]]:
    """Map Roboflow's COCO category ids to contiguous labels 0..N-1.
    Roboflow exports include an unused parent category, so only ids that
    actually appear in annotations become classes."""
    coco = json.loads((split_dir / ANNOTATIONS).read_text())
    names = {c["id"]: c["name"] for c in coco["categories"]}
    used = sorted({a["category_id"] for a in coco["annotations"]})
    cat_to_label = {cid: i for i, cid in enumerate(used)}
    id2label = {i: names[cid] for cid, i in cat_to_label.items()}
    return cat_to_label, id2label


class CocoDetection(Dataset):
    def __init__(self, split_dir: Path, cat_to_label: dict[int, int], train: bool, max_images: int | None):
        coco = json.loads((split_dir / ANNOTATIONS).read_text())
        self.dir = split_dir
        self.images = coco["images"][:max_images] if max_images else coco["images"]
        self.cat_to_label = cat_to_label
        self.train = train
        self.anns: dict[int, list] = {}
        for a in coco["annotations"]:
            if a["category_id"] in cat_to_label:
                self.anns.setdefault(a["image_id"], []).append(a)

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, i: int):
        info = self.images[i]
        image = Image.open(self.dir / info["file_name"]).convert("RGB")
        objects = []
        for a in self.anns.get(info["id"], []):
            x, y, w, h = a["bbox"]
            if w < 1 or h < 1:
                continue
            objects.append({"bbox": [x, y, w, h], "category_id": self.cat_to_label[a["category_id"]],
                            "area": w * h, "iscrowd": 0})
        # Light augmentation: horizontal flip (a pitch is left-right symmetric)
        if self.train and random.random() < 0.5:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            for o in objects:
                x, y, w, h = o["bbox"]
                o["bbox"] = [image.width - x - w, y, w, h]
        return image, {"image_id": info["id"], "annotations": objects}


def make_collate(processor):
    def collate(batch):
        images, targets = zip(*batch)
        enc = processor(images=list(images), annotations=list(targets), return_tensors="pt")
        return {
            "pixel_values": enc["pixel_values"],
            "labels": enc["labels"],
            "sizes": [(im.height, im.width) for im in images],
            "targets": list(targets),
        }
    return collate


# --------------------------------------------------------------------------- eval
@torch.no_grad()
def evaluate(model, processor, loader, device, id2label, amp) -> dict[str, float]:
    model.eval()
    metric = MeanAveragePrecision(box_format="xyxy", iou_type="bbox", class_metrics=True)
    for batch in loader:
        with torch.autocast(device.type, dtype=torch.float16, enabled=amp):
            outputs = model(pixel_values=batch["pixel_values"].to(device))
        results = processor.post_process_object_detection(outputs, threshold=0.01, target_sizes=batch["sizes"])
        preds, gts = [], []
        for r, t in zip(results, batch["targets"]):
            preds.append({"boxes": r["boxes"].float().cpu(), "scores": r["scores"].float().cpu(),
                          "labels": r["labels"].cpu()})
            boxes = [[x, y, x + w, y + h] for x, y, w, h in (o["bbox"] for o in t["annotations"])]
            gts.append({"boxes": torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4),
                        "labels": torch.tensor([o["category_id"] for o in t["annotations"]], dtype=torch.int64)})
        metric.update(preds, gts)
    m = metric.compute()
    scores = {"map": m["map"].item(), "map_50": m["map_50"].item(), "map_small": m["map_small"].item()}
    classes = m["classes"].reshape(-1).tolist()
    for cls, ap in zip(classes, m["map_per_class"].reshape(-1).tolist()):
        scores[f"map_{id2label[int(cls)]}"] = ap  # e.g. map_ball - the class to watch
    return scores


# --------------------------------------------------------------------------- registry
def register(run_id: str, score: float, dataset_version: str) -> None:
    client = MlflowClient()
    try:
        client.create_registered_model(MODEL_NAME, description="PitchVision player/ball detector (RT-DETRv2)")
    except MlflowException:
        pass  # already exists
    source = f"{mlflow.get_run(run_id).info.artifact_uri}/model"
    version = client.create_model_version(
        MODEL_NAME, source=source, run_id=run_id,
        tags={PRIMARY_METRIC: f"{score:.4f}", "dataset_version": dataset_version},
    )
    champion_score = None
    try:
        champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
        champion_score = client.get_run(champion.run_id).data.metrics.get(PRIMARY_METRIC)
    except MlflowException:
        pass  # no champion yet
    if champion_score is None or score > champion_score:
        client.set_registered_model_alias(MODEL_NAME, "champion", version.version)
        print(f"Registered {MODEL_NAME} v{version.version} as CHAMPION ({PRIMARY_METRIC}={score:.4f}, previous={champion_score})")
    else:
        client.set_registered_model_alias(MODEL_NAME, "challenger", version.version)
        print(f"Registered {MODEL_NAME} v{version.version} as challenger ({score:.4f} <= champion {champion_score:.4f})")


# --------------------------------------------------------------------------- train
def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    amp = device.type == "cuda" and not args.no_amp
    torch.backends.cudnn.benchmark = True
    print(f"Device: {torch.cuda.get_device_name(0) if device.type == 'cuda' else 'cpu'} | AMP: {amp}")

    data_dir = download_dataset(args.dataset_uri, Path(args.data_dir))
    manifest = json.loads((data_dir / "manifest.json").read_text())
    cat_to_label, id2label = load_label_map(data_dir / "train")
    print(f"Classes: {id2label}")

    processor = AutoImageProcessor.from_pretrained(
        args.checkpoint, size={"height": args.image_size, "width": args.image_size})
    model = AutoModelForObjectDetection.from_pretrained(
        args.checkpoint, id2label=id2label, label2id={v: k for k, v in id2label.items()},
        ignore_mismatched_sizes=True,  # new 4-class head replaces the 80-class COCO head
    ).to(device)

    collate = make_collate(processor)
    loaders = {
        s: DataLoader(CocoDetection(data_dir / s, cat_to_label, train=(s == "train"), max_images=args.max_images),
                      batch_size=args.batch_size, shuffle=(s == "train"),
                      num_workers=args.num_workers, collate_fn=collate)
        for s in SPLITS
    }
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs * len(loaders["train"]))
    scaler = torch.amp.GradScaler("cuda", enabled=amp)

    mlflow.set_experiment(args.experiment)
    with mlflow.start_run(run_name=args.run_name) as run:
        # Lineage: which code, which data, which starting weights, which hardware
        mlflow.set_tags({
            "image_git_sha": os.environ.get("IMAGE_GIT_SHA", "unknown"),
            "dataset_uri": args.dataset_uri,
            "dataset_version": manifest.get("version", "unknown"),
            "device": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
        })
        mlflow.log_params({k: v for k, v in vars(args).items() if k not in ("data_dir",)})
        mlflow.log_params({"num_classes": len(id2label), "train_images": len(loaders["train"].dataset)})
        mlflow.log_dict(manifest, "dataset/manifest.json")
        freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout
        mlflow.log_text(freeze, "environment/requirements-frozen.txt")

        for epoch in range(args.epochs):
            model.train()
            t0, total = time.time(), 0.0
            for batch in loaders["train"]:
                labels = [{k: v.to(device) for k, v in lab.items()} for lab in batch["labels"]]
                with torch.autocast(device.type, dtype=torch.float16, enabled=amp):
                    loss = model(pixel_values=batch["pixel_values"].to(device), labels=labels).loss
                optimizer.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.1)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                total += loss.item()
            train_loss = total / len(loaders["train"])
            mlflow.log_metrics({"train_loss": train_loss, "lr": scheduler.get_last_lr()[0],
                                "epoch_seconds": time.time() - t0}, step=epoch)
            print(f"epoch {epoch + 1}/{args.epochs}  loss {train_loss:.4f}  ({time.time() - t0:.0f}s)")
            if (epoch + 1) % args.eval_every == 0 or epoch + 1 == args.epochs:
                valid = evaluate(model, processor, loaders["valid"], device, id2label, amp)
                mlflow.log_metrics({f"valid_{k}": v for k, v in valid.items()}, step=epoch)
                print("  valid " + "  ".join(f"{k}={v:.3f}" for k, v in valid.items()))

        test = evaluate(model, processor, loaders["test"], device, id2label, amp)
        mlflow.log_metrics({f"test_{k}": v for k, v in test.items()})
        print("TEST  " + "  ".join(f"{k}={v:.3f}" for k, v in test.items()))

        with tempfile.TemporaryDirectory() as tmp:
            model.save_pretrained(tmp)
            processor.save_pretrained(tmp)
            mlflow.log_artifacts(tmp, artifact_path="model")

        if args.register:
            register(run.info.run_id, test["map"], manifest.get("version", "unknown"))


if __name__ == "__main__":
    main()
