"""Download a Roboflow Universe dataset version and write a provenance manifest.

Run once from a laptop; the dataset then lives in S3 and training reads it
from there (so the cluster never needs the Roboflow key, and training doesn't
depend on a third-party service being up).

Usage:
    read -s ROBOFLOW_API_KEY && export ROBOFLOW_API_KEY
    python scripts/data/fetch_roboflow_dataset.py --version 13
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = "roboflow-jvuqo"
PROJECT = "football-players-detection-3zvbc"
DATASET_NAME = "football-players-detection"
SOURCE_URL = f"https://universe.roboflow.com/{WORKSPACE}/{PROJECT}"
LICENSE = "CC BY 4.0"
ATTRIBUTION = f"football-players-detection dataset by Roboflow, Roboflow Universe, {SOURCE_URL}"
SPLITS = ("train", "valid", "test")
ANNOTATION_FILE = "_annotations.coco.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def summarise_split(split_dir: Path) -> dict:
    ann_path = split_dir / ANNOTATION_FILE
    coco = json.loads(ann_path.read_text())
    names = {c["id"]: c["name"] for c in coco["categories"]}
    per_class = Counter(names[a["category_id"]] for a in coco["annotations"])
    images_on_disk = [p for p in split_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES]
    return {
        "images": len(coco["images"]),
        "images_on_disk": len(images_on_disk),
        "annotations": len(coco["annotations"]),
        "annotations_per_class": dict(sorted(per_class.items())),
        "annotation_file_sha256": sha256(ann_path),
        "bytes": sum(p.stat().st_size for p in split_dir.iterdir() if p.is_file()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", type=int, required=True, help="Roboflow dataset version, e.g. 13")
    parser.add_argument("--out", default="data", help="Local output root (git-ignored)")
    args = parser.parse_args()

    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        sys.exit("ROBOFLOW_API_KEY is not set. Use: read -s ROBOFLOW_API_KEY && export ROBOFLOW_API_KEY")

    import roboflow  # imported late so --help works without the package

    dest = Path(args.out) / DATASET_NAME / f"v{args.version}"
    print(f"Downloading {WORKSPACE}/{PROJECT} v{args.version} (COCO JSON) to {dest} ...")
    rf = roboflow.Roboflow(api_key=api_key)
    rf.workspace(WORKSPACE).project(PROJECT).version(args.version).download(
        "coco", location=str(dest), overwrite=True
    )

    splits = {s: summarise_split(dest / s) for s in SPLITS if (dest / s / ANNOTATION_FILE).exists()}
    if set(splits) != set(SPLITS):
        sys.exit(f"Expected splits {SPLITS}, found {sorted(splits)} - check the download")

    classes = sorted({c for s in splits.values() for c in s["annotations_per_class"]})
    manifest = {
        "dataset": DATASET_NAME,
        "version": f"v{args.version}",
        "format": "COCO JSON",
        "source": {
            "platform": "Roboflow Universe",
            "workspace": WORKSPACE,
            "project": PROJECT,
            "version": args.version,
            "url": f"{SOURCE_URL}/dataset/{args.version}",
        },
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "classes": classes,
        "preprocessing_as_published": "Auto-orient; resize: stretch to 1280x1280 (16:9 frames squashed to square); no augmentation",
        "splits": splits,
        "totals": {
            "images": sum(s["images"] for s in splits.values()),
            "annotations": sum(s["annotations"] for s in splits.values()),
        },
        "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "tool": f"roboflow-python {getattr(roboflow, '__version__', 'unknown')}",
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(json.dumps({k: manifest[k] for k in ("version", "classes", "totals")}, indent=2))
    for name, s in splits.items():
        print(f"  {name:5}: {s['images']:4} images, {s['annotations']:5} boxes  {s['annotations_per_class']}")
    print(f"\nManifest written to {dest / 'manifest.json'}")


if __name__ == "__main__":
    main()
