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
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image

from detector import Detector, draw

MODEL_NAME = os.environ.get("MODEL_NAME", "pitchvision-detector")
MODEL_ALIAS = os.environ.get("MODEL_ALIAS", "champion")
DEFAULT_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.5"))

log = logging.getLogger("uvicorn.error")
state: dict = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fail fast: if the model can't load, the pod restarts and the error is in its logs
    detector = Detector(MODEL_NAME, MODEL_ALIAS)
    state["detector"] = detector
    log.info("Loaded %s v%s (@%s) on %s", MODEL_NAME, detector.info["version"], MODEL_ALIAS, detector.device)
    yield


app = FastAPI(title="PitchVision inference", lifespan=lifespan)


async def read_image(file: UploadFile) -> Image.Image:
    try:
        return Image.open(io.BytesIO(await file.read())).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read the upload as an image") from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": state["detector"].info["version"]}


@app.get("/model")
def model_info() -> dict:
    return state["detector"].info


@app.post("/predict")
async def predict(file: UploadFile = File(...),
                  threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0)) -> dict:
    image = await read_image(file)
    detections, elapsed_ms = state["detector"].detect(image, threshold)
    return {
        "model_version": state["detector"].info["version"],
        "inference_ms": round(elapsed_ms, 1),
        "image_size": [image.width, image.height],
        "counts": dict(Counter(d["label"] for d in detections)),
        "detections": detections,
    }


@app.post("/predict/annotated")
async def predict_annotated(file: UploadFile = File(...),
                            threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0)) -> Response:
    image = await read_image(file)
    detections, _ = state["detector"].detect(image, threshold)
    buffer = io.BytesIO()
    draw(image, detections).save(buffer, format="JPEG", quality=90)
    return Response(content=buffer.getvalue(), media_type="image/jpeg")
