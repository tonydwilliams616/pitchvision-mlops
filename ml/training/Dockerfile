# Training image. Placeholder for now - PR 4 switches the base to a CUDA/PyTorch
# image and adds the real RT-DETR fine-tuning code.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so code-only changes reuse this cached layer
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY train.py .

# Bake the Git commit into the image, so every run can log exactly which code it used
ARG GIT_SHA=unknown
ENV IMAGE_GIT_SHA=${GIT_SHA}

# Don't run as root
RUN useradd --create-home --uid 1000 trainer
USER trainer

ENTRYPOINT ["python", "train.py"]
