# PitchVision training image: RT-DETRv2 fine-tuning on CUDA.
# torch wheels from PyPI bundle the CUDA runtime, so a slim Python base is
# enough - the node's NVIDIA driver (580 / CUDA 13) runs CUDA 12.x builds.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

# Non-root user created early so it can own the model cache
RUN useradd --create-home --uid 1000 trainer

WORKDIR /app

# Heavy dependency layer first (several GB) so code-only changes reuse it
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the pretrained checkpoint into the image: training doesn't depend on
# Hugging Face being reachable, and the image pins exactly which weights it starts from
ARG CHECKPOINT=PekingU/rtdetr_v2_r18vd
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('${CHECKPOINT}')" \
    && chown -R trainer:trainer /opt/hf-cache

COPY train.py .

# The Git commit, logged to MLflow with every run
ARG GIT_SHA=unknown
ENV IMAGE_GIT_SHA=${GIT_SHA} \
    # Checkpoint is baked in above - never call the Hugging Face Hub at runtime
    HF_HUB_OFFLINE=1 \
    # No git in the image; the commit is already logged as image_git_sha
    GIT_PYTHON_REFRESH=quiet

USER trainer

ENTRYPOINT ["python", "train.py"]
