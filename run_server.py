#!/usr/bin/env python3
"""Launch a private localhost llama.cpp server for the local Qwen model."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def command(arguments: argparse.Namespace) -> list[str]:
    root = Path(__file__).resolve().parent
    default_server = root / ("runtime/llama-server.exe" if os.name == "nt" else "runtime/llama-server")
    server = arguments.server or default_server
    model = arguments.model or root / "models/Qwen3-30B-A3B-Q4_K_M.gguf"
    if not server.is_file():
        raise FileNotFoundError(f"llama-server not found: {server}; run setup_qwen.sh")
    if not model.is_file():
        raise FileNotFoundError(f"Qwen model not found: {model}; run setup_qwen.sh")
    return [
        str(server), "--model", str(model), "--host", arguments.host,
        "--port", str(arguments.port), "--ctx-size", str(arguments.context),
        "--threads", str(arguments.threads), "--n-gpu-layers", str(arguments.gpu_layers),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--threads", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--gpu-layers", type=int, default=0,
                        help="GPU layers to offload; the default 0 is CPU-only")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    try:
        invocation = command(arguments)
    except FileNotFoundError as exc:
        parser.error(str(exc))
    print("Starting local Qwen server:")
    print(" ".join(invocation))
    print(f"Browser: http://{arguments.host}:{arguments.port}")
    print("Stop it with Ctrl+C.")
    if arguments.dry_run:
        return
    if arguments.open_browser:
        webbrowser.open(f"http://{arguments.host}:{arguments.port}")
    try:
        raise SystemExit(subprocess.call(invocation))
    except KeyboardInterrupt:
        print("\nServer stopped.")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
