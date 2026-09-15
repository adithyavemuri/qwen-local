#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly MODEL_FILE="${QWEN_MODEL_FILE:-Qwen3-30B-A3B-Q4_K_M.gguf}"

if [[ ! -x "$PROJECT_DIR/runtime/llama-server" || ! -s "$PROJECT_DIR/models/$MODEL_FILE" ]]; then
  printf 'Runtime or model is missing; running local setup first.\n'
  "$PROJECT_DIR/setup_qwen.sh"
fi

exec python3 "$PROJECT_DIR/run_server.py" --open-browser "$@"

