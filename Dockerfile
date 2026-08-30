FROM python:3.14-slim@sha256:cae66f2ef0ec51a9891263eeee7f987dacf0a9879e8aa9353d5606e0530619a5

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
    && pip uninstall -y msgpack setuptools \
    && rm -f /usr/local/lib/python3.14/sbom.spdx.json

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY app/ ./app/

EXPOSE 3000
VOLUME ["/photos", "/data"]

ENTRYPOINT ["/entrypoint.sh"]
