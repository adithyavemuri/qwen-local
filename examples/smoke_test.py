#!/usr/bin/env python3
"""Load installed weights, check HTTP/UI and two short replies, then stop.

Run from qwen-local:
    python3 examples/smoke_test.py --preset qwen3.8-27b

No downloads, root access or external model API. Results go to logs/.
This checks installation, not general intelligence or scientific correctness.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model_config import catalog, model_ready, selection
from run_server import command, server_environment


def request(url, body=None, timeout=180):
    payload = None if body is None else json.dumps(body).encode()
    headers = {"Accept-Encoding": "gzip"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content = response.read()
        return gzip.decompress(content) if response.headers.get("Content-Encoding") == "gzip" else content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default=catalog()["default"], choices=list(catalog()["models"]))
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--backend", choices=("auto", "cpu", "vulkan"), default="auto")
    parser.add_argument("--context", type=int, default=4096)
    parser.add_argument("--benchmark", action="store_true",
                        help="Also request a longer response and record server decode tokens/second")
    args = parser.parse_args()
    if args.threads <= 0 or args.context <= 0:
        parser.error("threads and context must be positive")
    config = selection(args.preset)
    model = ROOT / "models" / config["filename"]
    if not model_ready(model, config):
        parser.error("Selected model is missing or incomplete. Complete setup first.")
    # Choose a free local port; binding can still race another process, in which
    # case the server exits and this test reports failure rather than killing it.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    invocation = command(argparse.Namespace(
        preset=args.preset, model=None, server=None, host="127.0.0.1", port=port,
        context=args.context, threads=args.threads, gpu_layers=None, thinking="off", backend=args.backend))
    backend = "vulkan" if "vulkan" in Path(invocation[0]).parts else "cpu"
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    report = {"preset": args.preset, "model": model.name, "runtime_ref": config["llama_ref"],
              "context": args.context, "threads": args.threads, "backend": backend, "thinking": "off",
              "checks": [], "success": False}
    if "--device" in invocation:
        report["device"] = invocation[invocation.index("--device") + 1]
    log_path = logs / f"{args.preset}-{backend}-server-test.log"
    report_path = logs / f"{args.preset}-{backend}-smoke-test.json"
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(invocation, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   env=server_environment(invocation[0]))
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError(f"Server exited with {process.returncode}; inspect {log_path.name}.")
                try:
                    status = json.loads(request(base + "/health", timeout=1))
                    if status.get("status") == "ok":
                        break
                except (OSError, urllib.error.URLError, ValueError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Model load timed out after approximately five minutes.")
            report["load_seconds"] = round(time.monotonic() - started, 3)
            report["checks"].append({"name": "health", "pass": True})
            index = request(base + "/").lower()
            if b"<html" not in index or b"<script" not in index:
                raise RuntimeError("Bundled browser interface was not served.")
            report["checks"].append({"name": "browser_html", "pass": True})
            models = json.loads(request(base + "/v1/models"))["data"]
            identifier = models[0]["id"]
            for prompt, expected in (("Reply with exactly LOCAL_QWEN_OK and no other text.", "LOCAL_QWEN_OK"),
                                     ("What is 19 times 23? Reply with only the integer.", "437")):
                began = time.monotonic()
                answer = json.loads(request(base + "/v1/chat/completions", {
                    "model": identifier, "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 32, "temperature": 0, "stream": False,
                }))
                text = answer["choices"][0]["message"].get("content") or ""
                passed = text.strip() == expected
                report["checks"].append({"name": expected, "pass": passed, "answer": text,
                                         "seconds": round(time.monotonic() - began, 3),
                                         "usage": answer.get("usage", {})})
                if not passed:
                    raise RuntimeError(f"Expected {expected!r}, received {text!r}.")
            if args.benchmark:
                answer = json.loads(request(base + "/v1/chat/completions", {
                    "model": identifier, "messages": [{"role": "user", "content":
                        "Explain how a Python context manager works, with a short file-reading example. "
                        "Write about 200 words."}],
                    "max_tokens": 256, "temperature": 0, "stream": False,
                }))
                report["benchmark"] = {
                    "prompt": "Python context manager explanation", "max_tokens": 256,
                    "usage": answer.get("usage", {}), "timings": answer.get("timings", {}),
                    "answer": answer["choices"][0]["message"].get("content", ""),
                }
            report["success"] = True
        except Exception as exc:
            report["error"] = str(exc)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            report["total_seconds"] = round(time.monotonic() - started, 3)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
            print(f"Saved: {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
