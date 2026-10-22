#!/usr/bin/env bash
# One model at a time. Press Ctrl+C before choosing another preset.
# Run from anywhere:
#   bash examples/chat.sh qwen3.5-4b
#   bash examples/chat.sh qwen3.8-27b
# Optional extra launcher settings follow the preset:
#   bash examples/chat.sh qwen3.5-4b --backend cpu --threads 6
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
PRESET="${1:-qwen3.5-4b}"
if (($#)); then shift; fi
exec bash "$PROJECT_DIR/start_qwen.sh" --preset "$PRESET" --thinking off "$@"
