"""A cross-encoder behind the /rerank contract text-embeddings-inference uses.

TEI itself would do, and on an amd64 or GPU host it should: swap the image in
compose.yaml and nothing here changes. TEI publishes no arm64 build, so on Apple
silicon it runs under emulation, which makes its latency meaningless to measure
against -- the same trap stage 13 hit comparing a GGUF model to a PyTorch one.

Scores are raw logits, not probabilities. Only their order is used.
"""

import os

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = os.environ.get("MODEL_ID", "BAAI/bge-reranker-v2-m3")
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", "512"))
BATCH = int(os.environ.get("BATCH_SIZE", "16"))

tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
torch.set_num_threads(int(os.environ.get("TORCH_THREADS", str(os.cpu_count() or 4))))

app = FastAPI(title="reranker")


class RerankRequest(BaseModel):
    query: str = Field(min_length=1)
    documents: list[str] = Field(min_length=1)
    model: str | None = None  # accepted and ignored; one model per container


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL}


@app.post("/rerank")
@torch.inference_mode()
def rerank(request: RerankRequest) -> list[dict]:
    scores: list[float] = []
    for start in range(0, len(request.documents), BATCH):
        pairs = [[request.query, document]
                 for document in request.documents[start:start + BATCH]]
        batch = tokenizer(pairs, padding=True, truncation=True,
                          max_length=MAX_LENGTH, return_tensors="pt")
        scores += model(**batch).logits.view(-1).float().tolist()
    # TEI's shape. The caller reads `index`, so the order of this list is free.
    return [{"index": index, "score": score} for index, score in enumerate(scores)]
