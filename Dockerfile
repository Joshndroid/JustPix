FROM python:3.14-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

ARG APT_CACHE_BUST=manual
RUN apt-get update \
    && echo "APT cache bust: ${APT_CACHE_BUST}" \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
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
