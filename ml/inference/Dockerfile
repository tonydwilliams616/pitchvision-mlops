# PitchVision inference service: serves the @champion model on CPU.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Pick up Debian security patches at build time (the training image's scan
# found HIGH findings in base packages)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app
WORKDIR /app

# CPU-only PyTorch: a fraction of the CUDA build's size, and the service runs
# on ordinary nodes rather than a GPU
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .

ARG GIT_SHA=unknown
ENV IMAGE_GIT_SHA=${GIT_SHA} \
    # The model comes from MLflow, never from the Hugging Face Hub
    HF_HUB_OFFLINE=1 \
    GIT_PYTHON_REFRESH=quiet

USER app
EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
