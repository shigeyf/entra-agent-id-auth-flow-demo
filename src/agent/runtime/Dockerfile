# Foundry Agent Service (Hosted Agent)
ARG AGENT_PLATFORM=linux/amd64
FROM --platform=$AGENT_PLATFORM python:3.11-slim

# Build context: src/agent/runtime/
#   docker build -t <image> -f src/agent/runtime/Dockerfile src/agent/runtime/
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8088
CMD ["python", "main.py"]
