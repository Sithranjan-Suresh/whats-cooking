# Build from the repo root:  docker build -f backend/Dockerfile -t whats-cooking-api .
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DATA_DIR=/data PORT=8000

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fontconfig ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY backend/assets backend/assets
COPY backend/docker-entrypoint.sh backend/docker-entrypoint.sh
COPY seed seed
COPY eval eval
COPY scripts scripts

# Register the bundled fonts with fontconfig so libass (burned captions) finds Oswald/Inter.
RUN mkdir -p /usr/share/fonts/truetype/app && cp backend/assets/fonts/*.ttf backend/assets/fonts/*.otf /usr/share/fonts/truetype/app/ \
 && fc-cache -f >/dev/null && chmod +x backend/docker-entrypoint.sh

VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health',timeout=4)"
ENTRYPOINT ["backend/docker-entrypoint.sh"]
