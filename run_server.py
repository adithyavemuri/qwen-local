#!/usr/bin/env python3
"""Launch local Qwen, Gemma or Phi chat, optionally with browser model switching."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from model_config import catalog, gpu_runtime, model_ready, runtime_ready, selection
import model_router


def command(arguments: argparse.Namespace) -> list[str]:
    root = Path(__file__).resolve().parent
    default_server = root / ("runtime/llama-server.exe" if os.name == "nt" else "runtime/llama-server")
    config = selection(arguments.preset)
    backend = getattr(arguments, "backend", "auto")
    gpu = gpu_runtime(config) if backend != "cpu" and not arguments.server else None
    if backend == "vulkan" and not gpu and not arguments.server:
        raise ValueError("Portable Vulkan runtime is not installed for this runtime pin; run python3 setup_gpu.py.")
    server = arguments.server or (gpu["executable"] if gpu else default_server)
    layers = arguments.gpu_layers
    if layers is None:
        layers = "auto" if gpu else 0
    if not gpu and not arguments.server and layers != 0:
        raise ValueError("The CPU runtime cannot offload GPU layers. Run setup_gpu.py or use --gpu-layers 0.")
    if not server.is_file():
        raise FileNotFoundError(f"llama-server not found: {server}; run setup_qwen.sh")
    if getattr(arguments, "router", False):
        if arguments.model:
            raise ValueError("--router cannot be combined with --model; use an installed catalog preset.")
        model_router.configuration(root, arguments.preset)
        model_options = ["--models-preset", str(model_router.config_path(root, arguments.port)),
                         "--models-max", "1", "--models-autoload", "--offline"]
    else:
        model = arguments.model or root / "models" / config["filename"]
        if not model.is_file():
            raise FileNotFoundError(f"Model not found: {model}; run setup_qwen.sh")
        model_options = ["--model", str(model)]
    device = getattr(arguments, "device", None) or (gpu.get("device") if gpu else None)
    device_options = ["--device", device] if device else []
    return [
        str(server), "--host", arguments.host,
        "--port", str(arguments.port), "--ctx-size", str(arguments.context or config["context"]),
        "--threads", str(arguments.threads), "--n-gpu-layers", str(layers),
        "--parallel", "1", "--jinja", "--no-agent", "--no-ui-mcp-proxy",
        "--cors-origins", "localhost", "--reasoning", arguments.thinking,
    ] + model_options + device_options


def server_environment(server: str, router: bool = False) -> dict:
    """Scope portable GPU library lookup to the child process only."""
    environment = os.environ.copy()
    if router:
        # Do not expose unrelated models from the user's global HF/llama cache.
        environment["LLAMA_CACHE"] = str(Path(__file__).resolve().parent / "runtime/router-cache")
        for key in ("LLAMA_ARG_MODEL", "LLAMA_ARG_MODEL_URL", "LLAMA_ARG_HF_REPO",
                    "LLAMA_ARG_HF_FILE", "LLAMA_ARG_HF_REPO_V", "LLAMA_ARG_MODELS_DIR"):
            environment.pop(key, None)
    gpu = gpu_runtime(selection())
    if gpu and Path(server).resolve() == gpu["executable"]:
        paths = [str(path) for path in gpu["libraries"]]
        if environment.get("LD_LIBRARY_PATH"):
            paths.append(environment["LD_LIBRARY_PATH"])
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(paths)
    return environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=list(catalog()["models"]),
                        help="Model preset (default: models.json or QWEN_MODEL_PRESET)")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--router", action="store_true",
                        help="Switch installed models in the browser; load at most one model, without downloads")
    parser.add_argument("--setup-if-needed", action="store_true",
                        help="Build/download missing preset components before starting")
    parser.add_argument("--server", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--context", type=int, help="Context tokens (preset default: 4096)")
    parser.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--backend", choices=("auto", "cpu", "vulkan"), default="auto",
                        help="Use an installed portable Vulkan GPU runtime when available; otherwise CPU")
    parser.add_argument("--gpu-layers", type=int,
                        help="GPU layers to offload (default: automatic fit on Vulkan, 0 on CPU)")
    parser.add_argument("--device", help="Override the installed GPU selection, e.g. Vulkan1")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--thinking", choices=("auto", "on", "off"), default="auto",
                        help="Keep model default, enable reasoning, or request direct answers")
    arguments = parser.parse_args()
    if arguments.list_models:
        subprocess.run([sys.executable, str(Path(__file__).with_name("model_config.py")),
                        "--list-models"], check=True)
        return
    if arguments.context is not None and arguments.context <= 0:
        parser.error("--context must be positive")
    if arguments.threads <= 0 or not 1 <= arguments.port <= 65535 or (
            arguments.gpu_layers is not None and arguments.gpu_layers < 0):
        parser.error("Use positive threads, port 1..65535 and non-negative GPU layers")
    try:
        config = selection(arguments.preset)
        root = Path(__file__).resolve().parent
        if arguments.setup_if_needed and not arguments.dry_run:
            available_gpu = arguments.backend != "cpu" and gpu_runtime(config)
            need_runtime = not arguments.server and not (runtime_ready(config) or available_gpu)
            need_model = not arguments.router and not arguments.model and not model_ready(
                root / "models" / config["filename"], config)
            if need_runtime or need_model:
                if os.name == "nt":
                    setup = ["powershell.exe", "-NoProfile", "-File", str(root / "setup_qwen.ps1"),
                             "-ModelPreset", config["preset"]]
                    stage = "-RuntimeOnly" if need_runtime else "-ModelOnly"
                else:
                    setup = ["bash", str(root / "setup_qwen.sh"), "--model", config["preset"]]
                    stage = "--runtime-only" if need_runtime else "--model-only"
                if not (need_runtime and need_model):
                    setup.append(stage)
                subprocess.run(setup, check=True)
        invocation = command(arguments)
        if arguments.router and not arguments.dry_run:
            model_router.prepare(root, arguments.port, arguments.preset)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print("Starting local model server:")
    print(" ".join(invocation))
    print(f"Browser: http://{arguments.host}:{arguments.port}")
    print("Stop it with Ctrl+C.")
    if arguments.router:
        print("Browser model switching enabled: installed models only, one loaded at a time.")
    if arguments.dry_run:
        return
    if arguments.open_browser:
        webbrowser.open(f"http://{arguments.host}:{arguments.port}")
    try:
        raise SystemExit(subprocess.call(invocation, env=server_environment(invocation[0], router=arguments.router)))
    except KeyboardInterrupt:
        print("\nServer stopped.")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
