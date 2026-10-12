FROM python:3.12-slim

# Zero external dependencies — stdlib only.
WORKDIR /app
COPY server.py .
COPY static/ ./static/

# /data   -> household CSVs (products, inventory)
# /config -> users.json, config.json (api key, OIDC settings)
RUN mkdir -p /data /config
ENV DATA_DIR=/data CONFIG_DIR=/config PORT=8000

EXPOSE 8000
CMD ["python", "server.py"]
