"""
GPU server for BAAI/bge-reranker-v2-m3 with the same TEI-compatible /rerank
endpoint as server.py, so RAGFlow's "HuggingFace" rerank factory can call it
in place of the CPU TEI container (which took minutes per batch here).

Run from the qwen-reranker image, mounting this file and the model:
  docker run -d --name bge-reranker-gpu --gpus all --network docker_ragflow \
    --network-alias ragflow-tei-rerank \
    -v C:/develop/tei_models/bge-reranker-v2-m3:/model \
    -v C:/develop/ragflow-main/qwen_reranker/bge_server.py:/app/bge_server.py \
    qwen-reranker:local uvicorn bge_server:app --host 0.0.0.0 --port 80
"""
import os
import logging
import threading
from typing import List

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bge-reranker")

MODEL_PATH = os.environ.get("RERANK_MODEL_PATH", "/model")
MAX_LEN = int(os.environ.get("RERANK_MAX_LEN", "1024"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

log.info(f"Loading {MODEL_PATH} on {DEVICE} ...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
).to(DEVICE).eval()
log.info("Model ready.")

# Same reason as server.py: sync endpoints run in a thread pool, and parallel
# forward passes on one CUDA model are not safe.
_GPU_LOCK = threading.Lock()

app = FastAPI()


class RerankRequest(BaseModel):
    query: str
    texts: List[str]
    raw_scores: bool = False
    truncate: bool = True


@torch.no_grad()
def _score_batch(query: str, docs: List[str]) -> List[float]:
    batch = tokenizer(
        [[query, d] for d in docs],
        padding=True,
        truncation=True,
        max_length=MAX_LEN,
        return_tensors="pt",
    ).to(DEVICE)
    logits = model(**batch).logits.view(-1).float()
    return torch.sigmoid(logits).cpu().tolist()


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_PATH, "device": DEVICE}


@app.post("/rerank")
def rerank(req: RerankRequest):
    if not req.texts:
        return []
    with _GPU_LOCK:
        scores = _score_batch(req.query, req.texts)
    return [{"index": i, "score": float(s)} for i, s in enumerate(scores)]
