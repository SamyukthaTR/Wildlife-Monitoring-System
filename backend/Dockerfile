FROM python:3.11-slim

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

# The application code will be mounted as a volume in development
# The entrypoint command is handled by docker-compose for hot reload
