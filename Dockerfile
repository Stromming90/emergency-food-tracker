FROM python:3.12-slim

# Zero external dependencies — stdlib only.
WORKDIR /app
COPY server.py .
COPY static/ ./static/

# Data lives in /data (mount as a volume, e.g. a TrueNAS dataset)
RUN mkdir -p /data
ENV DATA_DIR=/data PORT=8000

EXPOSE 8000
CMD ["python", "server.py"]
