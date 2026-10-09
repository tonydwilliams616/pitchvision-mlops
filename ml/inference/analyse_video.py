"""Analyse a football clip with the @champion detector.

1. Download the clip from S3
2. Run detection on every Nth frame (CPU-friendly sampling)
3. Write an annotated H.264 video and per-frame stats
4. Log params, summary metrics, stats and the video to MLflow, with lineage
   (which model version, which clip, which image)

Environment: MLFLOW_TRACKING_URI, AWS credentials (Pod Identity), IMAGE_GIT_SHA.
"""
import argparse
import os
import statistics
import tempfile
import time
from collections import Counter
from pathlib import Path

import boto3
import imageio.v2 as imageio
import mlflow
import numpy as np
from PIL import Image

from detector import Detector, draw


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video-uri", required=True, help="s3://bucket/key.mp4")
    p.add_argument("--model-name", default=os.environ.get("MODEL_NAME", "pitchvision-detector"))
    p.add_argument("--alias", default="champion")
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--every", type=int, default=5, help="Analyse every Nth frame")
    p.add_argument("--max-frames", type=int, default=0, help="Stop after N analysed frames (0 = whole clip)")
    p.add_argument("--experiment", default="pitchvision-video-analysis")
    p.add_argument("--run-name", default=None)
    return p.parse_args()


def download(uri: str, dest_dir: Path) -> Path:
    bucket, _, key = uri.removeprefix("s3://").partition("/")
    dest = dest_dir / Path(key).name
    boto3.client("s3").download_file(bucket, key, str(dest))
    print(f"Clip: downloaded {uri} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def main() -> None:
    args = parse_args()
    detector = Detector(args.model_name, args.alias)
    print(f"Model: {args.model_name} v{detector.info['version']} (@{args.alias}) on {detector.device}")

    work = Path(tempfile.mkdtemp())
    clip = download(args.video_uri, work)
    reader = imageio.get_reader(str(clip), "ffmpeg")
    source_fps = float(reader.get_meta_data().get("fps", 25.0))
    output_fps = max(1.0, round(source_fps / args.every, 2))
    annotated = work / "annotated.mp4"
    writer = imageio.get_writer(str(annotated), fps=output_fps, codec="libx264",
                                pixelformat="yuv420p", quality=7, macro_block_size=1)

    frames: list[dict] = []
    started = time.perf_counter()
    for index, frame in enumerate(reader):
        if index % args.every:
            continue
        image = Image.fromarray(frame).convert("RGB")
        detections, ms = detector.detect(image, args.threshold)
        counts = Counter(d["label"] for d in detections)
        balls = [d for d in detections if d["label"] == "ball"]
        ball = None
        if balls:
            best = max(balls, key=lambda d: d["score"])["box"]
            ball = [round((best[0] + best[2]) / 2, 1), round((best[1] + best[3]) / 2, 1)]
        frames.append({"frame": index, "time_s": round(index / source_fps, 2), "counts": dict(counts),
                       "ball_centre": ball, "inference_ms": round(ms, 1)})
        writer.append_data(np.asarray(draw(image, detections)))
        if len(frames) % 25 == 0:
            print(f"  {len(frames)} frames analysed ({index / source_fps:.1f}s of video)")
        if args.max_frames and len(frames) >= args.max_frames:
            break
    writer.close()
    reader.close()
    elapsed = time.perf_counter() - started
    if not frames:
        raise SystemExit("No frames were analysed - check the clip")

    def mean_count(label: str) -> float:
        return round(statistics.mean(f["counts"].get(label, 0) for f in frames), 2)

    summary = {
        "frames_analysed": len(frames),
        "clip_seconds": round(frames[-1]["time_s"], 2),
        "avg_players": mean_count("player"),
        "avg_goalkeepers": mean_count("goalkeeper"),
        "avg_referees": mean_count("referee"),
        "ball_visible_pct": round(100 * sum(f["ball_centre"] is not None for f in frames) / len(frames), 1),
        "avg_inference_ms": round(statistics.mean(f["inference_ms"] for f in frames), 1),
        "processing_seconds": round(elapsed, 1),
    }

    mlflow.set_experiment(args.experiment)
    with mlflow.start_run(run_name=args.run_name):
        # Lineage: which model analysed which clip, with which code
        mlflow.set_tags({
            "model_name": args.model_name,
            "model_version": detector.info["version"],
            "model_run_id": detector.info["run_id"],
            "video_uri": args.video_uri,
            "image_git_sha": os.environ.get("IMAGE_GIT_SHA", "unknown"),
        })
        mlflow.log_params({"alias": args.alias, "threshold": args.threshold, "every": args.every,
                           "source_fps": source_fps, "output_fps": output_fps})
        mlflow.log_metrics(summary)
        mlflow.log_dict(summary, "stats/summary.json")
        mlflow.log_dict({"frames": frames}, "stats/per_frame.json")
        mlflow.log_artifact(str(annotated), artifact_path="video")

    print("SUMMARY  " + "  ".join(f"{k}={v}" for k, v in summary.items()))


if __name__ == "__main__":
    main()
