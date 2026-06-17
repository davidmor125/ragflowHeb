"""Add MORE debug to retrieval.py — specifically embd model + the actual retriever call args."""

with open('/ragflow/agent/tools/retrieval.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Print which embd model and rerank model are being used
old = "        embd_mdl = None\n        if embd_nms:\n            tenant_id = self._canvas.get_tenant_id()\n            embd_model_config = get_model_config_by_type_and_name(tenant_id, LLMType.EMBEDDING, embd_nms[0])\n            embd_mdl = LLMBundle(tenant_id, embd_model_config)\n"
new = (
    "        embd_mdl = None\n"
    "        if embd_nms:\n"
    "            tenant_id = self._canvas.get_tenant_id()\n"
    "            print(f'[DBG-RTR] embd_nms={embd_nms} tenant_id={tenant_id}', flush=True)\n"
    "            embd_model_config = get_model_config_by_type_and_name(tenant_id, LLMType.EMBEDDING, embd_nms[0])\n"
    "            print(f'[DBG-RTR] embd_model_config keys={list((embd_model_config or {{}}).keys()) if embd_model_config else None}', flush=True)\n"
    "            embd_mdl = LLMBundle(tenant_id, embd_model_config)\n"
)
if old not in src:
    print("ERROR: marker not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)

# Print rerank info too
old2 = "        rerank_mdl = None\n        if self._param.rerank_id:\n            rerank_model_config = get_model_config_by_type_and_name(kbs[0].tenant_id, LLMType.RERANK, self._param.rerank_id)\n            rerank_mdl = LLMBundle(kbs[0].tenant_id, rerank_model_config)\n"
new2 = (
    "        rerank_mdl = None\n"
    "        print(f'[DBG-RTR] rerank_id={self._param.rerank_id!r}', flush=True)\n"
    "        if self._param.rerank_id:\n"
    "            rerank_model_config = get_model_config_by_type_and_name(kbs[0].tenant_id, LLMType.RERANK, self._param.rerank_id)\n"
    "            rerank_mdl = LLMBundle(kbs[0].tenant_id, rerank_model_config)\n"
)
if old2 not in src:
    print("ERROR: marker 2 not found")
    raise SystemExit(1)
src = src.replace(old2, new2, 1)

# Print exact args passed to settings.retriever.retrieval
old3 = "            print(f'[DBG-RTR] about to retrieve, query={query[:80]!r} kbs={len(kbs)} top_n={self._param.top_n} sim={self._param.similarity_threshold} kw_w={self._param.keywords_similarity_weight}', flush=True)\n"
new3 = (
    "            print(f'[DBG-RTR] about to retrieve, query={query[:80]!r} kbs={len(kbs)} top_n={self._param.top_n} sim={self._param.similarity_threshold} kw_w={self._param.keywords_similarity_weight}', flush=True)\n"
    "            print(f'[DBG-RTR] tenant_ids_for_retrieval={[kb.tenant_id for kb in kbs]} filtered_kb_ids={filtered_kb_ids}', flush=True)\n"
    "            print(f'[DBG-RTR] embd_mdl={embd_mdl} rerank_mdl={rerank_mdl}', flush=True)\n"
)
if old3 not in src:
    print("ERROR: marker 3 not found")
    raise SystemExit(1)
src = src.replace(old3, new3, 1)

with open('/ragflow/agent/tools/retrieval.py', 'w', encoding='utf-8') as f:
    f.write(src)

print("retrieval.py patched again OK")
