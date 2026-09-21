FROM python:3.12-slim

# CPU wheels only: this runs beside OpenSearch on a dev machine, and the CUDA
# variants pull gigabytes that never get used.
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      torch transformers fastapi uvicorn

COPY app.py /app/app.py
WORKDIR /app

# Weights come from the mounted HF cache rather than the image, so the image
# stays small and switching MODEL_ID needs no rebuild.
ENV HF_HOME=/hf MODEL_ID=BAAI/bge-reranker-v2-m3 HF_HUB_OFFLINE=1
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=30 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
