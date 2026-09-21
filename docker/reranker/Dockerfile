FROM python:3.12-slim

# CPU용 휠만: 이는 개발 환경에서 OpenSearch와 함께 실행되며, CUDA 버전은 사용되지 않는 수 GB의 데이터를 다운로드한다.
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      torch transformers fastapi uvicorn

COPY app.py /app/app.py
WORKDIR /app

# 가중치는 이미지가 아닌 마운트된 HF 캐시에서 가져오므로, 이미지는 작게 유지되고 MODEL_ID를 변경할 때 재ビルド가 필요하지 않다.
ENV HF_HOME=/hf MODEL_ID=BAAI/bge-reranker-v2-m3 HF_HUB_OFFLINE=1
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=30 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
