#!/usr/bin/env bash
# Restart Ollama when it stops answering embedding requests.
#
# Why: Ollama can hang with a model still listed as loaded (seen after a GPU
# power-down): /api/ps answers, but every /api/embed blocks forever. RAGFlow
# embeds every query and every chunk through it, so search and parsing stop
# with no error anywhere. A process check does not catch this; a real
# embedding request does.
#
# Install on the Ollama host (Linux, Ollama as the systemd service "ollama"):
#   sudo cp ollama_watchdog.sh /usr/local/bin/ && sudo chmod +x /usr/local/bin/ollama_watchdog.sh
#   sudo crontab -e   ->   */5 * * * * /usr/local/bin/ollama_watchdog.sh
#
# Settings (environment): OLLAMA_URL, EMBED_MODEL (the model RAGFlow embeds
# with), TIMEOUT seconds, STATE file for the consecutive-failure count.
set -u
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
EMBED_MODEL="${EMBED_MODEL:-bge-m3}"
TIMEOUT="${TIMEOUT:-60}"
STATE="${STATE:-/var/tmp/ollama_watchdog.fails}"

if curl -sf -m "$TIMEOUT" "$OLLAMA_URL/api/embed" \
     -d "{\"model\":\"$EMBED_MODEL\",\"input\":\"healthcheck\"}" -o /dev/null; then
  echo 0 > "$STATE"
  exit 0
fi

fails=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 ))
echo "$fails" > "$STATE"
logger -t ollama_watchdog "embedding check failed ($fails in a row)"
# Two failures in a row (a cold model load can take one slot), then restart.
if [ "$fails" -ge 2 ]; then
  logger -t ollama_watchdog "restarting ollama"
  systemctl restart ollama
  echo 0 > "$STATE"
fi
