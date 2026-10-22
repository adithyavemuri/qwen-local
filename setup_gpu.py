#!/usr/bin/env python3
"""Install pinned portable Vulkan binaries locally; no root, SDK or pip needed.

Linux x86-64 only. Requires an existing compatible Vulkan GPU driver and curl.
The existing locally compiled CPU runtime is kept as a separate fallback.
"""
from __future__ import annotations

import hashlib
import ctypes.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile

from model_config import ROOT, catalog, gpu_runtime, selection


def download(archive: dict, tag: str) -> Path:
    destination = ROOT / "downloads" / archive["filename"]
    destination.parent.mkdir(exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if not destination.is_file():
        url = f"https://github.com/ggml-org/llama.cpp/releases/download/{tag}/{destination.name}"
        print(f"Downloading {destination.name} ({archive['size_bytes'] / 1e6:.0f} MB)...", flush=True)
        subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                        "--retry", "5", "--continue-at", "-", "--output", str(partial), url], check=True)
        source = partial
    else:
        source = destination
    if source.stat().st_size != archive["size_bytes"]:
        raise ValueError(f"Wrong archive size: {source.name}")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != archive["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {source.name}; archive was not extracted.")
    if source == partial:
        partial.rename(destination)
    print(f"Verified {destination.name}", flush=True)
    return destination


def extract(archive: Path, destination: Path) -> None:
    """Extract ordinary files/directories first, then safe in-tree symlinks."""
    root = destination.resolve()
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        for member in members:
            path = root / member.name
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"Unsafe archive path: {member.name}")
            if member.issym():
                if not (path.parent / member.linkname).resolve().is_relative_to(root):
                    raise ValueError(f"Unsafe archive symlink: {member.name}")
            elif not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsupported archive member: {member.name}")
        for member in members:
            path = root / member.name
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, path.open("wb") as target:
                    shutil.copyfileobj(source, target)
                path.chmod(member.mode & 0o777)
        for member in members:
            if member.issym():
                path = root / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(member.linkname)
                if not path.resolve().is_relative_to(root):
                    raise ValueError(f"Unsafe resolved archive symlink: {member.name}")


def main() -> None:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("Portable GPU setup currently supports Linux x86-64 only.")
    if not shutil.which("curl") or not ctypes.util.find_library("vulkan"):
        raise SystemExit("curl and an existing Vulkan loader/GPU driver are required.")
    model = selection()
    config = catalog()["runtime"]
    if model["llama_ref"] != config["ref"]:
        raise SystemExit("Portable GPU archives support only the catalog's pinned runtime.")
    if gpu_runtime(model):
        print("Matching portable GPU runtime is already installed.")
        return
    destination = ROOT / "runtime/vulkan"
    if destination.exists():
        raise SystemExit("runtime/vulkan already exists but does not match; refusing to overwrite it.")
    archives = [download(item, config["vulkan_linux"]["tag"]) for item in config["vulkan_linux"]["archives"]]
    destination.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gpu-install-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "payload"
        stage.mkdir()
        for archive in archives:
            extract(archive, stage)
        servers = list(stage.rglob("llama-server"))
        if len(servers) != 1:
            raise ValueError("Expected exactly one llama-server in the portable archives.")
        server = servers[0]
        paths = sorted({path.parent for path in stage.rglob("*.so*") if path.is_file()})
        environment = os.environ.copy()
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            [str(path) for path in paths] + [environment.get("LD_LIBRARY_PATH", "")])
        version = subprocess.check_output([str(server), "--version"], env=environment,
                                          stderr=subprocess.STDOUT, text=True)
        if config["commit"][:7] not in version:
            raise ValueError(f"Portable runtime commit does not match: {version}")
        devices = subprocess.check_output([str(server), "--list-devices"], env=environment,
                                          stderr=subprocess.STDOUT, text=True)
        print(devices, flush=True)
        if "Vulkan0" not in devices:
            raise ValueError("Portable runtime did not detect a Vulkan GPU; CPU runtime is untouched.")
        candidates = re.findall(r"^\s*(Vulkan\d+): (.+)$", devices, re.MULTILINE)
        candidates = [(key, name) for key, name in candidates
                      if not any(software in name.lower() for software in ("llvmpipe", "lavapipe", "software"))]
        if not candidates:
            raise ValueError("Only software Vulkan devices were detected; CPU runtime is untouched.")
        # Prefer NVIDIA over an integrated Intel GPU on hybrid laptops. Users
        # can override this choice with the launcher's --device option.
        device = next((key for key, name in candidates if "NVIDIA" in name), candidates[0][0])
        (stage / "build-manifest.json").write_text(json.dumps({
            "ref": config["ref"], "commit": config["commit"], "backend": "vulkan",
            "binary_tag": config["vulkan_linux"]["tag"],
            "server": str(server.relative_to(stage)),
            "device": device,
            "library_paths": [str(path.relative_to(stage)) for path in paths],
            "archives": config["vulkan_linux"]["archives"],
        }, indent=2) + "\n", encoding="utf-8")
        stage.rename(destination)
    print("Portable Vulkan runtime installed. Launcher --backend auto will use it.")


if __name__ == "__main__":
    main()
