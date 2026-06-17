# Local Qwen3-Reranker-4B server for RAGFlow (TEI-compatible /rerank endpoint).
# PyTorch 2.7+/CUDA 12.8 is required for Blackwell GPUs (sm_120) such as the
# RTX PRO 5000 — earlier CUDA builds raise "no kernel image available".
FROM pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime

WORKDIR /app

RUN pip install --no-cache-dir \
    "transformers>=4.51.0" \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "accelerate>=0.30"

COPY server.py /app/server.py

# HF cache persists via a mounted volume so the model is downloaded only once.
ENV HF_HOME=/models
ENV RERANK_MODEL=Qwen/Qwen3-Reranker-4B

EXPOSE 80
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "80"]
