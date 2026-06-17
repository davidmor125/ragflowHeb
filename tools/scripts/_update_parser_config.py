"""Update hozrim KB parser_config for better Hebrew chunking."""
import json, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

KB_ID = "dc0091ca46e211f196f633ac796a3d7a"

# Read current
out = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-N", "-D", "rag_flow"],
    input=f"SELECT parser_config FROM knowledgebase WHERE id='{KB_ID}';".encode(),
    capture_output=True,
)
raw = out.stdout.decode("utf-8").strip()
cfg = json.loads(raw)

# Apply Hebrew-friendly changes
cfg["chunk_token_num"] = 1024
cfg["delimiter"] = "\n!?.;。；！？"
cfg.setdefault("parent_child", {})
cfg["parent_child"]["use_parent_child"] = True
cfg["parent_child"]["children_delimiter"] = "\n!?.;。；！？"
cfg["children_delimiter"] = "\n!?.;。；！？"

new_json = json.dumps(cfg, ensure_ascii=False)
sql_safe = new_json.replace("\\", "\\\\").replace("'", "\\'")

sql = f"UPDATE knowledgebase SET parser_config = '{sql_safe}' WHERE id = '{KB_ID}';"
result = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-D", "rag_flow"],
    input=sql.encode("utf-8"),
    capture_output=True,
)
print("update returncode:", result.returncode)
print("stderr:", result.stderr.decode("utf-8", errors="replace"))

# Verify
verify = subprocess.run(
    ["docker", "exec", "-i", "docker-mysql-1",
     "mysql", "-u", "root", "-pinfini_rag_flow",
     "--default-character-set=utf8mb4", "-N", "-D", "rag_flow"],
    input=f"SELECT parser_config FROM knowledgebase WHERE id='{KB_ID}';".encode(),
    capture_output=True,
)
new_cfg = json.loads(verify.stdout.decode("utf-8").strip())
print("\n=== AFTER ===")
print(f"chunk_token_num: {new_cfg.get('chunk_token_num')}")
print(f"delimiter: {new_cfg.get('delimiter')!r}")
print(f"parent_child.use_parent_child: {new_cfg['parent_child']['use_parent_child']}")
print(f"parent_child.children_delimiter: {new_cfg['parent_child']['children_delimiter']!r}")
