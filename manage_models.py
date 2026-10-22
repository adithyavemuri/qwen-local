#!/usr/bin/env python3
"""Choose, download, verify and launch local models. Standard library only."""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys

from model_config import ROOT, catalog, model_ready, selection, verify_model


def setup_command(preset: str, windows: bool | None = None) -> list[str]:
    windows = os.name == "nt" if windows is None else windows
    if windows:
        return ["powershell.exe", "-NoProfile", "-File", str(ROOT / "setup_qwen.ps1"),
                "-ModelPreset", preset, "-ModelOnly"]
    return ["bash", str(ROOT / "setup_qwen.sh"), "--model", preset, "--model-only"]


def launch_command(preset: str | None = None, browser: bool = False) -> list[str]:
    command = [sys.executable, str(ROOT / "run_server.py"), "--setup-if-needed",
               "--open-browser", "--thinking", "off"]
    return command + (["--router"] if browser else ["--preset", preset])


def show_models() -> None:
    data = catalog()
    print("\nLocal model catalog: weights download only when you choose to install")
    for index, (key, model) in enumerate(data["models"].items(), 1):
        installed = model_ready(ROOT / "models" / model["filename"], model)
        default = " [default]" if key == data["default"] else ""
        print(f"{index}. {key}{default}: {model['size_bytes'] / 1e9:.2f} GB; "
              f"{'installed' if installed else 'not installed'}")
    print(f"Free disk here: {shutil.disk_usage(ROOT).free / 1e9:.1f} GB")
    if hasattr(os, "sysconf"):
        try:
            memory = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1024**3
            print(f"Host RAM: {memory:.1f} GiB (total, not necessarily available)")
        except (OSError, ValueError):
            pass
    print("Context/runtime need memory beyond the weights. RAM fit does not guarantee fast chat.")
    print("No drivers are installed or changed.")


def run(command: list[str], dry_run: bool = False) -> int:
    print("\n" + (subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)), flush=True)
    return 0 if dry_run else subprocess.call(command, cwd=ROOT)


def install(preset: str, yes: bool = False, dry_run: bool = False) -> int:
    model = selection(preset)
    path = ROOT / "models" / model["filename"]
    print(f"\n{model['name']}\n{model.get('notes', '')}")
    print(f"Publisher: {model['repository']}; weights: {model['size_bytes'] / 1e9:.2f} GB")
    print(f"License: {model.get('license', 'check model card')}; "
          f"source: {model.get('original_model', model['url'])}")
    if dry_run:
        return run(setup_command(preset), dry_run=True)
    if not model_ready(path, model):
        partial = path.with_name(path.name + ".part")
        remaining = max(0, model["size_bytes"] - (partial.stat().st_size if partial.is_file() else 0))
        if remaining > shutil.disk_usage(ROOT).free:
            raise ValueError("Insufficient free disk for the remaining model download.")
        if not yes and input("Download these weights locally? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled. Nothing downloaded.")
            return 1
    return run(setup_command(preset))


def start(preset: str, yes: bool = False, dry_run: bool = False) -> int:
    model = selection(preset)
    if not dry_run and not model_ready(ROOT / "models" / model["filename"], model):
        result = install(preset, yes=yes)
        if result:
            return result
    print("A missing CPU runtime is compiled locally; host build prerequisites are required.")
    return run(launch_command(preset), dry_run=dry_run)


def browser(dry_run: bool = False) -> int:
    if not dry_run and not any(model_ready(ROOT / "models" / model["filename"], model)
                               for model in catalog()["models"].values()):
        raise ValueError("Install at least one catalog model before starting browser switching.")
    return run(launch_command(browser=True), dry_run=dry_run)


def menu() -> int:
    keys = list(catalog()["models"])
    while True:
        show_models()
        answer = input("\nChoose a model number, B for browser switching, or Q to quit: ").strip().lower()
        if answer == "q":
            return 0
        if answer == "b":
            browser()
            continue
        if not answer.isdigit() or not 1 <= int(answer) <= len(keys):
            print("Please choose a listed number, B or Q.")
            continue
        preset = keys[int(answer) - 1]
        print(f"\n{preset}: {catalog()['models'][preset].get('notes', '')}")
        action = input("1 = install/verify weights, 2 = launch chat, 3 = full checksum check, Enter = back: ").strip()
        if action == "1":
            install(preset)
        elif action == "2":
            start(preset)
        elif action == "3":
            model = selection(preset)
            verify_model(ROOT / "models" / model["filename"], model)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--list", action="store_true", help="Show sizes and installed status without downloading")
    actions.add_argument("--install", choices=list(catalog()["models"]), metavar="PRESET",
                         help="Download and verify one catalog model (asks before missing-weight downloads)")
    actions.add_argument("--start", choices=list(catalog()["models"]), metavar="PRESET",
                         help="Launch one model, asking before a missing-weight download")
    actions.add_argument("--browser", action="store_true", help="Switch installed models in the browser")
    parser.add_argument("--yes", action="store_true", help="Confirm an explicitly selected model download")
    parser.add_argument("--dry-run", action="store_true", help="Print a non-interactive command without executing it")
    args = parser.parse_args()
    if args.dry_run and not (args.install or args.start or args.browser):
        parser.error("--dry-run needs --install, --start or --browser")
    try:
        if args.list:
            show_models()
            return 0
        if os.environ.get("QWEN_MODEL_FILE") or os.environ.get("QWEN_MODEL_URL"):
            raise ValueError("Clear custom QWEN_MODEL_FILE/URL overrides before using the catalog manager.")
        if args.install:
            return install(args.install, yes=args.yes, dry_run=args.dry_run)
        if args.start:
            return start(args.start, yes=args.yes, dry_run=args.dry_run)
        if args.browser:
            return browser(dry_run=args.dry_run)
        return menu()
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
