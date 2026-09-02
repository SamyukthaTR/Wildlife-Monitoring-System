FROM python:3.11-slim AS base

WORKDIR /app

# ffmpeg + libsndfile1: MP3/OGG decoding for librosa/soundfile.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Model weights are cached here, backed by the wildlife_models volume, so they
# survive rebuilds and are downloaded once.
ENV HF_HOME=/app/model_cache/huggingface \
    TORCH_HOME=/app/model_cache/torch \
    YOLO_CONFIG_DIR=/app/model_cache/ultralytics \
    MPLCONFIGDIR=/app/model_cache/matplotlib \
    TRANSFORMERS_NO_TF=1 \
    OMP_NUM_THREADS=2

COPY requirements.txt .

# ultralytics depends on opencv-python, which pulls libGL. We want the headless
# build instead; both install a `cv2` module, so drop the non-headless one after
# resolution and reinstall headless to guarantee it is the surviving cv2.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python opencv-contrib-python || true \
    && pip install --no-cache-dir opencv-python-headless==4.10.0.84

# --- Production image: bakes in the application code and runs without
# --reload, as a non-root user. Used by docker-compose.prod.yml.
FROM base AS prod
RUN useradd --create-home --shell /bin/bash appuser
COPY . .
RUN mkdir -p uploads model_cache && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# --- Development image (default build target). Application code and the run
# command come from docker-compose.yml's bind mount and command override, not
# from this image, so plain `docker build` / `docker compose up` keep working
# exactly as before.
FROM base AS dev
