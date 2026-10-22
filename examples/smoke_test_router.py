#!/usr/bin/env python3
"""Test local browser model routing: small -> large -> small, no downloads.

Run: python3 examples/smoke_test_router.py
Both named presets must already be installed. Results go to logs/.
Starts its own localhost router on a free port and stops its own children.
It never stops a server you launched yourself. This tests HTTP switching, not
automated browser clicking or scientific/coding answer quality.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import model_router
from model_config import model_ready, selection
from run_server import command, server_environment
from smoke_test import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--small", default="qwen3.5-4b")
    parser.add_argument("--large", default="qwen3.8-27b")
    parser.add_argument("--models", nargs="+",
                        help="Optional explicit switching sequence, overriding --small/--large")
    parser.add_argument("--backend", choices=("auto", "cpu", "vulkan"), default="auto")
    args = parser.parse_args()
    sequence = args.models or (args.small, args.large, args.small)
    for key in sequence:
        spec = selection(key)
        if not model_ready(ROOT / "models" / spec["filename"], spec):
            parser.error(f"{key} is not installed; no download is performed by this test.")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    options = argparse.Namespace(preset=sequence[0], model=None, server=None, backend=args.backend,
                                 router=True, host="127.0.0.1", port=port, context=4096,
                                 threads=8, gpu_layers=None, thinking="off")
    invocation = command(options)
    ini = model_router.prepare(ROOT, port, sequence[0])
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    report = {"success": False, "sequence": [], "backend": args.backend, "context": 4096}
    started = time.monotonic()
    with (logs / "router-server-test.log").open("w") as log:
        process = subprocess.Popen(invocation, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   env=server_environment(invocation[0], router=True),
                                   start_new_session=os.name != "nt")
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(180):
                if process.poll() is not None:
                    raise RuntimeError("Router exited; inspect logs/router-server-test.log.")
                try:
                    data = json.loads(request(base + "/models", timeout=2))["data"]
                    break
                except (OSError, ValueError):
                    time.sleep(1)
            else:
                raise RuntimeError("Router startup timed out.")
            report["models"] = [item["id"] for item in data]
            if not set(sequence).issubset(report["models"]):
                raise RuntimeError(f"Installed presets not advertised: {report['models']}")
            if b"<html" not in request(base + "/").lower():
                raise RuntimeError("Browser interface was not served.")
            report["browser_html"] = True
            for key in sequence:
                began = time.monotonic()
                answer = json.loads(request(base + "/v1/chat/completions", {
                    "model": key, "messages": [{"role": "user", "content":
                        "What is 19 times 23? Reply with only the integer."}],
                    "max_tokens": 16, "temperature": 0, "stream": False,
                }, timeout=300))
                text = answer["choices"][0]["message"].get("content", "").strip()
                states = json.loads(request(base + "/models"))["data"]
                active = [item["id"] for item in states
                          if item["status"]["value"] in ("loading", "loaded", "sleeping")]
                record = {"requested": key, "served": answer.get("model"), "answer": text,
                          "active": active, "seconds": round(time.monotonic() - began, 3)}
                report["sequence"].append(record)
                if text != "437" or active != [key] or answer.get("model") != key:
                    raise RuntimeError(f"Switch failed: {record}")
            try:
                request(base + "/v1/chat/completions", {
                    "model": "not-installed-model", "messages": [{"role": "user", "content": "hello"}],
                    "max_tokens": 1,
                })
                raise RuntimeError("Router unexpectedly accepted a non-installed model.")
            except urllib.error.HTTPError as error:
                if error.code not in (400, 404):
                    raise
                report["missing_model_http_status"] = error.code
            report["success"] = True
        except Exception as error:
            report["error"] = str(error)
            raise
        finally:
            if process.poll() is None:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait()
            ini.unlink(missing_ok=True)
            report["seconds"] = round(time.monotonic() - started, 3)
            (logs / "router-smoke-test.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
