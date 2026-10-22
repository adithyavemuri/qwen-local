#!/usr/bin/env python3
"""Shared model selection and integrity checks; Python standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent


def catalog() -> dict:
    return json.loads((ROOT / "models.json").read_text(encoding="utf-8"))


def selection(preset: str | None = None) -> dict:
    data = catalog()
    key = preset or os.environ.get("QWEN_MODEL_PRESET") or data["default"]
    if key not in data["models"]:
        raise ValueError(f"Unknown preset {key!r}. Choose: {', '.join(data['models'])}")
    model = dict(data["models"][key], preset=key)
    model["url"] = (f"https://huggingface.co/{model['repository']}/resolve/"
                    f"{model['revision']}/{model['filename']}")
    if os.environ.get("QWEN_MODEL_FILE") or os.environ.get("QWEN_MODEL_URL"):
        model["filename"] = os.environ.get("QWEN_MODEL_FILE") or model["filename"]
        if not os.environ.get("QWEN_MODEL_URL"):
            raise ValueError("A custom QWEN_MODEL_FILE requires QWEN_MODEL_URL; use --model for an existing local file.")
        model["url"] = os.environ["QWEN_MODEL_URL"]
        model["sha256"] = os.environ.get("QWEN_MODEL_SHA256", "").lower()
        model["size_bytes"] = int(os.environ.get("QWEN_MODEL_SIZE", "0"))
        model["repository"] = "custom"
        model["revision"] = "custom"
    filename = model["filename"]
    if filename in {"", ".", ".."} or any(c in filename for c in ("/", "\\", "\r", "\n")) or not filename.endswith(".gguf"):
        raise ValueError("Model filename must be a plain .gguf filename, not a path.")
    if model["sha256"] and not re.fullmatch(r"[0-9a-f]{64}", model["sha256"]):
        raise ValueError("Model SHA-256 must contain 64 hexadecimal characters.")
    if not model["url"].startswith("https://") or any(c in model["url"] for c in ("\r", "\n")):
        raise ValueError("Model download URL must use HTTPS and contain no newlines.")
    if model["size_bytes"] < 0:
        raise ValueError("Model size must not be negative.")
    model["llama_ref"] = os.environ.get("LLAMA_CPP_REF") or data["runtime"]["ref"]
    model["llama_commit"] = (data["runtime"]["commit"]
                             if model["llama_ref"] == data["runtime"]["ref"] else "")
    return model


def model_ready(path: Path, model: dict) -> bool:
    return path.is_file() and path.stat().st_size > 0 and (
        not model["size_bytes"] or path.stat().st_size == model["size_bytes"])


def verify_file(path: Path, spec: dict) -> None:
    """Verify a downloaded tool/archive against local size and SHA-256 pins."""
    if not path.is_file() or path.stat().st_size != spec["size_bytes"]:
        raise ValueError(f"Wrong size or missing file: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != spec["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.name}; file was NOT accepted.")
    print(f"SHA-256 verified: {path.name}")


def verify_model(path: Path, model: dict) -> None:
    if not model_ready(path, model):
        raise ValueError(f"Model is absent or has the wrong size: {path.name}; expected {model['size_bytes']} bytes.")
    with path.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError(f"Not a GGUF file: {path.name}")
        if not model["sha256"]:
            print("WARNING: custom model has no pinned SHA-256; only size and GGUF header were checked.")
            return
        stream.seek(0)
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != model["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path.name}; file was NOT accepted.")
    print(f"SHA-256 verified: {path.name}")


def runtime_ready(model: dict) -> bool:
    executable = ROOT / "runtime" / ("llama-server.exe" if os.name == "nt" else "llama-server")
    try:
        manifest = json.loads((ROOT / "runtime/build-manifest.json").read_text())
    except (OSError, ValueError):
        return False
    return executable.is_file() and manifest.get("ref") == model["llama_ref"] and (
        not model["llama_commit"] or manifest.get("commit") == model["llama_commit"])


def gpu_runtime(model: dict) -> dict | None:
    """Return a matching, explicitly installed portable Vulkan runtime, if any."""
    root = ROOT / "runtime/vulkan"
    try:
        manifest = json.loads((root / "build-manifest.json").read_text())
        if manifest.get("backend") != "vulkan" or manifest.get("ref") != model["llama_ref"] or (
                model["llama_commit"] and manifest.get("commit") != model["llama_commit"]):
            return None
        server = (root / manifest["server"]).resolve()
        paths = [(root / path).resolve() for path in manifest["library_paths"]]
        if not server.is_relative_to(root.resolve()) or not server.is_file():
            return None
        if not all(path.is_relative_to(root.resolve()) and path.is_dir() for path in paths):
            return None
        return dict(manifest, executable=server, libraries=paths)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset")
    parser.add_argument("--tool", choices=list(catalog()["tools"]), help="Inspect/verify a pinned build tool")
    parser.add_argument("--field")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--runtime-ready", action="store_true")
    parser.add_argument("--write-runtime-manifest", action="store_true")
    args = parser.parse_args()
    try:
        if args.tool:
            if args.preset or args.list_models or args.runtime_ready or args.write_runtime_manifest:
                raise ValueError("--tool cannot be combined with model/runtime operations.")
            spec = catalog()["tools"][args.tool]
            if args.verify:
                verify_file(args.verify, spec)
            elif args.field:
                print(spec[args.field])
            else:
                print(json.dumps(spec))
            return
        if args.list_models:
            data = catalog()
            for key, value in data["models"].items():
                marker = " (default)" if key == data["default"] else ""
                installed = model_ready(ROOT / "models" / value["filename"], value)
                print(f"{key}{marker}: {value['name']}; {value['size_bytes'] / 1e9:.2f} GB; "
                      f"{'installed' if installed else 'not installed'}")
            return
        model = selection(args.preset)
        if args.verify:
            verify_model(args.verify, model)
        elif args.runtime_ready:
            raise SystemExit(0 if runtime_ready(model) else 1)
        elif args.write_runtime_manifest:
            commit = subprocess.check_output(["git", "-C", str(ROOT / "build/llama.cpp"),
                                              "rev-parse", "HEAD"], text=True).strip()
            if model["llama_commit"] and commit != model["llama_commit"]:
                raise ValueError("Runtime source commit does not match the catalog pin.")
            (ROOT / "runtime/build-manifest.json").write_text(json.dumps({
                "ref": model["llama_ref"], "commit": commit, "backend": "cpu",
                "build_type": "Release", "shared_libraries": False,
            }, indent=2) + "\n", encoding="utf-8")
        elif args.field:
            if args.field not in model:
                raise ValueError(f"Unknown configuration field: {args.field}")
            print(model[args.field])
        else:
            print(json.dumps(model))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
