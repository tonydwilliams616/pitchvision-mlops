"""PitchVision inference service.

Serves whichever model holds the alias (default: champion) in the MLflow model
registry. The model is resolved and downloaded at startup, so promoting a new
champion needs only a restart - no code or image change.

Endpoints:
  GET  /health              liveness/readiness + loaded version
  GET  /model               lineage of the loaded model
  POST /predict             image -> JSON detections and per-class counts
  POST /predict/annotated   image -> JPEG with boxes drawn (demo)
"""
import io
import logging
import os
import tempfile
import time
from collections import Counter
from contextlib import asynccontextmanager

import mlflow
import torch
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from mlflow.tracking import MlflowClient
from PIL import Image, ImageDraw
from transformers import AutoImageProcessor, AutoModelForObjectDetection

MODEL_NAME = os.environ.get("MODEL_NAME", "pitchvision-detector")
MODEL_ALIAS = os.environ.get("MODEL_ALIAS", "champion")
DEFAULT_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.5"))
COLOURS = {"ball": "yellow", "goalkeeper": "cyan", "player": "lime", "referee": "magenta"}

log = logging.getLogger("uvicorn.error")
state: dict = {}


def load_model() -> None:
    """Resolve the alias in the registry, download that version, load it."""
    client = MlflowClient()
    version = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
    run = client.get_run(version.run_id)
    local_dir = mlflow.artifacts.download_artifacts(artifact_uri=version.source, dst_path=tempfile.mkdtemp())

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor = AutoImageProcessor.from_pretrained(local_dir)
    model = AutoModelForObjectDetection.from_pretrained(local_dir).to(device).eval()

    state.update(model=model, processor=processor, device=device, info={
        "model_name": MODEL_NAME,
        "alias": MODEL_ALIAS,
        "version": version.version,
        "run_id": version.run_id,
        "test_map": run.data.metrics.get("test_map"),
        "test_map_ball": run.data.metrics.get("test_map_ball"),
        "image_size": run.data.params.get("image_size"),
        "training_image_sha": run.data.tags.get("image_git_sha"),
        "dataset_version": run.data.tags.get("dataset_version"),
        "service_image_sha": os.environ.get("IMAGE_GIT_SHA", "unknown"),
        "device": str(device),
    })
    log.info("Loaded %s v%s (@%s) on %s", MODEL_NAME, version.version, MODEL_ALIAS, device)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fail fast: if the model can't load, the pod restarts and the error is in its logs
    load_model()
    yield


app = FastAPI(title="PitchVision inference", lifespan=lifespan)


async def read_image(file: UploadFile) -> Image.Image:
    try:
        return Image.open(io.BytesIO(await file.read())).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read the upload as an image") from exc


@torch.no_grad()
def detect(image: Image.Image, threshold: float) -> tuple[list[dict], float]:
    processor, model = state["processor"], state["model"]
    inputs = processor(images=image, return_tensors="pt").to(state["device"])
    started = time.perf_counter()
    outputs = model(**inputs)
    result = processor.post_process_object_detection(
        outputs, threshold=threshold, target_sizes=[(image.height, image.width)])[0]
    elapsed_ms = (time.perf_counter() - started) * 1000
    labels = model.config.id2label
    detections = [
        {"label": labels[int(label)], "score": round(float(score), 4),
         "box": [round(float(v), 1) for v in box]}  # x1, y1, x2, y2 in pixels
        for score, label, box in zip(result["scores"], result["labels"], result["boxes"])
    ]
    return detections, elapsed_ms


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": state["info"]["version"]}


@app.get("/model")
def model_info() -> dict:
    return state["info"]


@app.post("/predict")
async def predict(file: UploadFile = File(...),
                  threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0)) -> dict:
    image = await read_image(file)
    detections, elapsed_ms = detect(image, threshold)
    return {
        "model_version": state["info"]["version"],
        "inference_ms": round(elapsed_ms, 1),
        "image_size": [image.width, image.height],
        "counts": dict(Counter(d["label"] for d in detections)),
        "detections": detections,
    }


@app.post("/predict/annotated")
async def predict_annotated(file: UploadFile = File(...),
                            threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0)) -> Response:
    image = await read_image(file)
    detections, _ = detect(image, threshold)
    draw = ImageDraw.Draw(image)
    for d in detections:
        colour = COLOURS.get(d["label"], "white")
        draw.rectangle(d["box"], outline=colour, width=3)
        draw.text((d["box"][0], max(0, d["box"][1] - 12)), f"{d['label']} {d['score']:.2f}", fill=colour)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return Response(content=buffer.getvalue(), media_type="image/jpeg")
