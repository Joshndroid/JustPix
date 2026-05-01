FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libheif-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY app/ ./app/

EXPOSE 3000
VOLUME ["/photos", "/thumbcache", "/config"]

ENTRYPOINT ["/entrypoint.sh"]
