FROM python:3.14-slim@sha256:44dd04494ee8f3b538294360e7c4b3acb87c8268e4d0a4828a6500b1eff50061

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libheif-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY app/ ./app/

EXPOSE 3000
VOLUME ["/photos", "/data"]

ENTRYPOINT ["/entrypoint.sh"]
