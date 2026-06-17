"""Add debug prints to retrieval.py inside container."""

with open('/ragflow/agent/tools/retrieval.py', 'r', encoding='utf-8') as f:
    src = f.read()

# 1) After _invoke_async entry - what is query / dataset_ids
old1 = "    async def _invoke_async(self, **kwargs):\n        if self.check_if_canceled(\"Retrieval processing\"):\n            return\n        if not kwargs.get(\"query\"):\n"
new1 = (
    "    async def _invoke_async(self, **kwargs):\n"
    "        import sys\n"
    "        print(f'[DBG-RTR] _invoke_async kwargs.keys={list(kwargs.keys())} query={str(kwargs.get(\"query\",\"\"))[:80]!r}', flush=True)\n"
    "        print(f'[DBG-RTR] dataset_ids={self._dataset_ids}', flush=True)\n"
    "        if self.check_if_canceled(\"Retrieval processing\"):\n            return\n"
    "        if not kwargs.get(\"query\"):\n"
)
if old1 not in src:
    print("ERROR: marker 1 not found")
    raise SystemExit(1)
src = src.replace(old1, new1, 1)

# 2) Right before kbinfos retrieval call - log query
old2 = "        if kbs:\n            query = re.sub(r\"^user[:：\\s]*\", \"\", query, flags=re.IGNORECASE)\n            kbinfos = await settings.retriever.retrieval(\n"
new2 = (
    "        if kbs:\n            query = re.sub(r\"^user[:：\\s]*\", \"\", query, flags=re.IGNORECASE)\n"
    "            print(f'[DBG-RTR] about to retrieve, query={query[:80]!r} kbs={len(kbs)} top_n={self._param.top_n} sim={self._param.similarity_threshold} kw_w={self._param.keywords_similarity_weight}', flush=True)\n"
    "            kbinfos = await settings.retriever.retrieval(\n"
)
if old2 not in src:
    print("ERROR: marker 2 not found")
    raise SystemExit(1)
src = src.replace(old2, new2, 1)

# 3) After kbinfos retrieved - count chunks
old3 = "                rerank_mdl=rerank_mdl,\n                rank_feature=label_question(query, kbs),\n            )\n            if self.check_if_canceled(\"Retrieval processing\"):\n                return\n"
new3 = (
    "                rerank_mdl=rerank_mdl,\n                rank_feature=label_question(query, kbs),\n            )\n"
    "            print(f'[DBG-RTR] retrieved chunks={len(kbinfos.get(\"chunks\",[]))}', flush=True)\n"
    "            if self.check_if_canceled(\"Retrieval processing\"):\n                return\n"
)
if old3 not in src:
    print("ERROR: marker 3 not found")
    raise SystemExit(1)
src = src.replace(old3, new3, 1)

# 4) Right before final set_output - what's form_cnt size
old4 = "        form_cnt = \"\\n\".join(kb_prompt(kbinfos, 200000, True))\n\n        # Set both formalized content and JSON output\n        self.set_output(\"formalized_content\", form_cnt)\n"
new4 = (
    "        form_cnt = \"\\n\".join(kb_prompt(kbinfos, 200000, True))\n"
    "        print(f'[DBG-RTR] form_cnt len={len(form_cnt)}', flush=True)\n"
    "\n        # Set both formalized content and JSON output\n        self.set_output(\"formalized_content\", form_cnt)\n"
)
if old4 not in src:
    print("ERROR: marker 4 not found")
    raise SystemExit(1)
src = src.replace(old4, new4, 1)

# 5) Empty paths
old5 = "        if not kbinfos[\"chunks\"]:\n            self.set_output(\"formalized_content\", self._param.empty_response)\n            return\n"
new5 = (
    "        if not kbinfos[\"chunks\"]:\n"
    "            print(f'[DBG-RTR] EMPTY chunks path -> set empty_response', flush=True)\n"
    "            self.set_output(\"formalized_content\", self._param.empty_response)\n            return\n"
)
if old5 not in src:
    print("ERROR: marker 5 not found")
    raise SystemExit(1)
src = src.replace(old5, new5, 1)

with open('/ragflow/agent/tools/retrieval.py', 'w', encoding='utf-8') as f:
    f.write(src)

print("retrieval.py patched OK")
