"""
Local Qwen3-Reranker-4B server, exposing the TEI-compatible /rerank endpoint
that RAGFlow's "HuggingFace" rerank factory (HuggingfaceRerank) calls.

Request (from RAGFlow):  POST /rerank
  {"query": str, "texts": [str, ...], "raw_scores": false, "truncate": true}
Response (TEI format):
  [{"index": int, "score": float}, ...]

This plays the exact same role for Qwen3-Reranker that the TEI container plays
for bge-reranker — RAGFlow treats it as a native rerank model in the UI dropdown.
"""
import os
import math
import logging
import threading
from typing import List

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("qwen-reranker")

MODEL_NAME = os.environ.get("RERANK_MODEL", "Qwen/Qwen3-Reranker-4B")
MAX_LEN = int(os.environ.get("RERANK_MAX_LEN", "4096"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Qwen3-Reranker is a causal LM used as a yes/no relevance judge. The official
# usage formats query+document into an instruction template and reads the
# probability of the "yes" token at the final position.
PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements based "
    "on the Query and the Instruct provided. Note that the answer can only be "
    '"yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
# Qwen3-Reranker is instruction-aware; a task-specific instruction is
# recommended over the generic default. Override with RERANK_INSTRUCT.
INSTRUCT = os.environ.get("RERANK_INSTRUCT", "Given a web search query, retrieve relevant passages that answer the query")
# FastAPI runs sync endpoints in a thread pool, so concurrent /rerank calls ran
# forward passes on the one CUDA model in parallel; the container then died
# with "CUDA error: an illegal memory access" and failed every later call.
# Serialize GPU work.
_GPU_LOCK = threading.Lock()

log.info(f"Loading {MODEL_NAME} on {DEVICE} ...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, padding_side="left")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
).to(DEVICE).eval()

# token ids for "yes"/"no" judgments
TOKEN_YES = tokenizer.convert_tokens_to_ids("yes")
TOKEN_NO = tokenizer.convert_tokens_to_ids("no")
PREFIX_IDS = tokenizer.encode(PREFIX, add_special_tokens=False)
SUFFIX_IDS = tokenizer.encode(SUFFIX, add_special_tokens=False)
log.info(f"Model ready. yes={TOKEN_YES} no={TOKEN_NO}")

app = FastAPI()


class RerankRequest(BaseModel):
    query: str
    texts: List[str]
    raw_scores: bool = False
    truncate: bool = True


def _format_pair(query: str, doc: str) -> str:
    return f"<Instruct>: {INSTRUCT}\n<Query>: {query}\n<Document>: {doc}"


@torch.no_grad()
def _score_batch(query: str, docs: List[str]) -> List[float]:
    pairs = [_format_pair(query, d) for d in docs]
    # tokenize the middle, then wrap with prefix/suffix ids, left-pad
    enc = tokenizer(
        pairs,
        add_special_tokens=False,
        max_length=MAX_LEN - len(PREFIX_IDS) - len(SUFFIX_IDS),
        truncation=True,
    )
    input_ids = [PREFIX_IDS + ids + SUFFIX_IDS for ids in enc["input_ids"]]
    batch = tokenizer.pad(
        {"input_ids": input_ids},
        padding=True,
        return_tensors="pt",
    ).to(DEVICE)
    logits = model(**batch).logits[:, -1, :]  # last-position logits
    yes = logits[:, TOKEN_YES]
    no = logits[:, TOKEN_NO]
    # softmax over (no, yes) -> probability of "yes"
    probs = torch.stack([no, yes], dim=1).softmax(dim=1)[:, 1]
    return probs.float().cpu().tolist()


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "device": DEVICE}


@app.post("/rerank")
def rerank(req: RerankRequest):
    if not req.texts:
        return []
    with _GPU_LOCK:
        scores = _score_batch(req.query, req.texts)
    return [{"index": i, "score": float(s)} for i, s in enumerate(scores)]
