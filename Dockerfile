FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

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
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && pip uninstall -y msgpack setuptools

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY app/ ./app/

EXPOSE 3000
VOLUME ["/photos", "/data"]

ENTRYPOINT ["/entrypoint.sh"]
