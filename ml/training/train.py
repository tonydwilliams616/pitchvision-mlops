"""PitchVision training entrypoint - placeholder.

Proves the image builds, runs, and can log to MLflow with full lineage.
PR 4 replaces the body with RT-DETR fine-tuning on the football dataset.
"""
import os
import platform

import mlflow


def main() -> None:
    git_sha = os.environ.get("IMAGE_GIT_SHA", "unknown")
    print(f"PitchVision training image | git sha: {git_sha} | python {platform.python_version()}")

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        print("MLFLOW_TRACKING_URI not set - skipping MLflow logging")
        return

    mlflow.set_experiment("pitchvision-image-smoke-test")
    with mlflow.start_run(run_name="image-smoke-test"):
        # Lineage: which image (and therefore which code) produced this run
        mlflow.set_tag("image_git_sha", git_sha)
        mlflow.log_param("placeholder", True)
    print(f"Logged a run to {tracking_uri}")


if __name__ == "__main__":
    main()
