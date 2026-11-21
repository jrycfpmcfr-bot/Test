# Image de l'application recette_video (Render, Railway, Fly.io…)
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY recette_video/requirements.txt recette_video/requirements.txt
RUN pip install --no-cache-dir -r recette_video/requirements.txt

# Modèle de transcription téléchargé dès la construction : pas d'attente au premier usage.
# "base" tient dans 1 Go de mémoire ; "small" est plus précis mais demande ~2 Go.
ARG WHISPER_MODEL=base
ENV WHISPER_MODEL=${WHISPER_MODEL}
RUN python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8')"

COPY recette_video recette_video

ENV HOST=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "recette_video"]
