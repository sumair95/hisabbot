FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps:
#   ffmpeg — audio preprocessing pipeline (HPF, denoise, loudnorm, silence trim)
#   build-essential — needed to compile the webrtcvad native extension
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY db ./db

EXPOSE 8000

# Use $PORT if set (Railway/Fly/Heroku), else 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
