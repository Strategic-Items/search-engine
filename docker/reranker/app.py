"""/rerank 계약 텍스트-임베딩 인퍼런스 뒤에 크로스-엔코더를 사용한다.

TEI 자체도 가능하며, amd64 또는 GPU 호스트에서는 다음과 같이 수행해야 한다: compose.yaml에 이미지를 교체하고 여기서는 아무것도 변경하지 않는다. TEI는 arm64 빌드를 출시하지 않으므로 Apple 실리콘에서는 에뮬레이션을 통해 실행되며, 이는 지연 시간을 비교하는 데 의미가 없다 -- 같은 함정 단계 13이 GGUF 모델과 PyTorch 모델을 비교할 때 발생한 것과 같다.

점수는 원시 로짓이며 확률이 아니다. 오직 그 순서만 사용된다.
"""

import os

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = os.environ.get("MODEL_ID", "BAAI/bge-reranker-v2-m3")
# 컨테이너 내부에서는 항상 cpu이다 -- Docker Desktop은 가속기를 전달하지 않는다
# 통과. 호스트에 하나가 있는 경우 이 파일을 직접 실행할 때 설정하세요; 그게 의미 있는 지연 시간을 측정할 수 있는 유일한 방법입니다.
# 수락되고 무시됨; 컨테이너당 하나의 모델
DEVICE = os.environ.get("DEVICE") or (
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available() else "cpu")
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", "512"))
BATCH = int(os.environ.get("BATCH_SIZE", "16"))

tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL).to(DEVICE).eval()
torch.set_num_threads(int(os.environ.get("TORCH_THREADS", str(os.cpu_count() or 4))))

app = FastAPI(title="reranker")


class RerankRequest(BaseModel):
    query: str = Field(min_length=1)
    documents: list[str] = Field(min_length=1)
    model: str | None = None  # TEI의 형태. 호출자가 `index`를 읽으므로 이 목록의 순서는 자유롭습니다.


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL, "device": DEVICE}


@app.post("/rerank")
@torch.inference_mode()
def rerank(request: RerankRequest) -> list[dict]:
    scores: list[float] = []
    for start in range(0, len(request.documents), BATCH):
        pairs = [[request.query, document]
                 for document in request.documents[start:start + BATCH]]
        batch = tokenizer(pairs, padding=True, truncation=True,
                          max_length=MAX_LENGTH, return_tensors="pt").to(DEVICE)
        scores += model(**batch).logits.view(-1).float().cpu().tolist()
    # TEI의 형태. 호출자는 `index`를 읽으므로 이 리스트의 순서는 자유롭다.
    return [{"index": index, "score": score} for index, score in enumerate(scores)]
