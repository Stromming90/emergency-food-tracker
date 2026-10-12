FROM python:3.12-slim

# Zero external dependencies — stdlib only.
WORKDIR /app
COPY server.py .
COPY static/ ./static/

# /data   -> global products.csv + household inventory CSVs
# /config -> users.json, config.json (api key, OIDC settings)
RUN mkdir -p /data /config
ENV DATA_DIR=/data CONFIG_DIR=/config PORT=4500

EXPOSE 4500
CMD ["python", "server.py"]
