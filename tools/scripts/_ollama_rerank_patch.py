"""
Local-only OllamaRerank patch. NOT for production.

Ollama doesn't expose a true cross-encoder reranker API. We approximate it
by computing cosine similarity between query and document embeddings via
Ollama's /api/embed. For production: use Jina/Xinference/LocalAI/Cohere.
"""

with open("/ragflow/rag/llm/rerank_model.py", "r", encoding="utf-8") as f:
    content = f.read()

if "class OllamaRerank" in content:
    print("already patched, skipping")
    raise SystemExit(0)

ollama_class = '''

class OllamaRerank(Base):
    """LOCAL-EVAL ONLY. Approximates rerank scores via /api/embed cosine.
    Not a true cross-encoder reranker - Ollama lacks that API surface.
    For production use Jina, Xinference, or LocalAI rerank backends."""
    _FACTORY_NAME = "Ollama"

    def __init__(self, key="x", model_name="", base_url=""):
        if not base_url:
            base_url = "http://host.docker.internal:11434"
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    def _embed(self, text: str) -> np.ndarray:
        url = urljoin(self.base_url + "/", "api/embed")
        r = requests.post(url, json={"model": self.model_name, "input": text}, timeout=120)
        r.raise_for_status()
        emb = r.json()["embeddings"][0]
        v = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def similarity(self, query: str, texts: list):
        try:
            q_vec = self._embed(query)
            scores = np.zeros(len(texts), dtype=float)
            tokens = num_tokens_from_string(query)
            for i, t in enumerate(texts):
                t_short = truncate(t, 8000)
                d_vec = self._embed(t_short)
                scores[i] = float(np.dot(q_vec, d_vec))
                tokens += num_tokens_from_string(t_short)
            return scores, tokens
        except Exception as e:
            log_exception(e)
            return np.zeros(len(texts), dtype=float), 0

'''

content = content.rstrip() + ollama_class + "\n"

with open("/ragflow/rag/llm/rerank_model.py", "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED OllamaRerank class added")
