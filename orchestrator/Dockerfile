# Stage 1: Build the mobile-enhanced index.html using ttyd
FROM tsl0922/ttyd:latest AS html-builder
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY build-index.py /tmp/build-index.py
RUN python3 /tmp/build-index.py

# Stage 2: Python orchestrator
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-built terminal HTML (mobile toolbar injected at build time)
COPY --from=html-builder /opt/ttyd/index.html /app/static/index.html

COPY main.py .

EXPOSE 8080
CMD ["python", "main.py"]
