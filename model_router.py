"""Generate local-only llama.cpp router presets from installed catalog models."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from model_config import catalog, model_ready, selection


def configuration(root: Path, preset: str | None = None, context: int | None = None,
                  contexts: dict[str, int] | None = None) -> str:
    if context is not None and (not isinstance(context, int) or isinstance(context, bool) or context <= 0):
        raise ValueError("Context tokens must be a positive integer.")
    if contexts is not None and any(not isinstance(value, int) or isinstance(value, bool) or value <= 0
                                    for value in contexts.values()):
        raise ValueError("Per-model context tokens must be positive integers.")
    if os.environ.get("QWEN_MODEL_FILE") or os.environ.get("QWEN_MODEL_URL"):
        raise ValueError("Router mode uses the model catalog; clear custom QWEN_MODEL_FILE/URL overrides.")
    installed = []
    for key in catalog()["models"]:
        if contexts is not None and key not in contexts:
            continue  # Automatic preflight could not establish a usable plan.
        model = selection(key)
        path = (root / "models" / model["filename"]).resolve()
        if model_ready(path, model):
            if any(char in str(path) for char in "\r\n"):
                raise ValueError("Model paths must not contain newlines.")
            installed.append((key, path, model))
    if not installed:
        raise ValueError("No complete catalog models are installed. Run setup_qwen.sh (or setup_qwen.ps1) first.")
    requested = preset or os.environ.get("QWEN_MODEL_PRESET")
    if requested and requested not in {key for key, _, _ in installed}:
        raise ValueError(f"Startup preset {requested!r} is not installed; download it explicitly using setup first.")
    preferred = requested or catalog()["default"]
    if preferred not in {key for key, _, _ in installed}:
        preferred = installed[0][0]
    lines = ["version = 1", ""]
    for key, path, model in installed:
        lines.extend([
            f"[{key}]", f"model = {path}",
            f"ctx-size = {contexts[key] if contexts is not None else context if context is not None else model['context']}",
            f"load-on-startup = {'true' if key == preferred else 'false'}", "",
        ])
    return "\n".join(lines)


def config_path(root: Path, port: int) -> Path:
    return root / "runtime" / f"router-models-{port}-{os.getpid()}.ini"


def prepare(root: Path, port: int, preset: str | None = None, context: int | None = None,
            contexts: dict[str, int] | None = None) -> Path:
    content = configuration(root, preset, context, contexts)
    destination = config_path(root, port)
    destination.parent.mkdir(parents=True, exist_ok=True)
    (root / "runtime/router-cache").mkdir(exist_ok=True)
    # Never expose a partially written INI if the server refreshes its presets.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                     prefix="router-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
