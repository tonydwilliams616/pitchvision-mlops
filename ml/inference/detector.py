"""Shared model loading and detection, used by the web service and the video job.

The model is whichever version holds the alias in the MLflow registry, downloaded
through MLflow's artifact proxy - so neither caller needs storage credentials.
"""
import os
import tempfile
import time

import mlflow
import torch
from mlflow.tracking import MlflowClient
from PIL import Image, ImageDraw
from transformers import AutoImageProcessor, AutoModelForObjectDetection

COLOURS = {"ball": "yellow", "goalkeeper": "cyan", "player": "lime", "referee": "magenta"}


class Detector:
    def __init__(self, model_name: str, alias: str):
        client = MlflowClient()
        version = client.get_model_version_by_alias(model_name, alias)
        run = client.get_run(version.run_id)
        local_dir = mlflow.artifacts.download_artifacts(artifact_uri=version.source, dst_path=tempfile.mkdtemp())

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoImageProcessor.from_pretrained(local_dir)
        self.model = AutoModelForObjectDetection.from_pretrained(local_dir).to(self.device).eval()
        self.labels = self.model.config.id2label
        self.info = {
            "model_name": model_name,
            "alias": alias,
            "version": version.version,
            "run_id": version.run_id,
            "test_map": run.data.metrics.get("test_map"),
            "test_map_ball": run.data.metrics.get("test_map_ball"),
            "image_size": run.data.params.get("image_size"),
            "training_image_sha": run.data.tags.get("image_git_sha"),
            "dataset_version": run.data.tags.get("dataset_version"),
            "service_image_sha": os.environ.get("IMAGE_GIT_SHA", "unknown"),
            "device": str(self.device),
        }

    @torch.no_grad()
    def detect(self, image: Image.Image, threshold: float) -> tuple[list[dict], float]:
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        started = time.perf_counter()
        outputs = self.model(**inputs)
        result = self.processor.post_process_object_detection(
            outputs, threshold=threshold, target_sizes=[(image.height, image.width)])[0]
        elapsed_ms = (time.perf_counter() - started) * 1000
        detections = [
            {"label": self.labels[int(label)], "score": round(float(score), 4),
             "box": [round(float(v), 1) for v in box]}  # x1, y1, x2, y2 in pixels
            for score, label, box in zip(result["scores"], result["labels"], result["boxes"])
        ]
        return detections, elapsed_ms


def draw(image: Image.Image, detections: list[dict]) -> Image.Image:
    """Draw boxes and labels onto the image (in place) and return it."""
    canvas = ImageDraw.Draw(image)
    for d in detections:
        colour = COLOURS.get(d["label"], "white")
        canvas.rectangle(d["box"], outline=colour, width=3)
        canvas.text((d["box"][0], max(0, d["box"][1] - 12)), f"{d['label']} {d['score']:.2f}", fill=colour)
    return image
