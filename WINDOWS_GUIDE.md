# Windows setup

**Compatibility implemented; end-to-end testing deferred.** Syntax checks do
not prove successful compilation, GPU operation or browser model switching.

The Windows installer is a PowerShell counterpart to `setup_qwen.sh`. It keeps
the source, compiled runtime, downloads, and model inside this folder.

## One-time prerequisites

Install:

1. Windows 10 or 11 on x64 hardware.
2. Python 3.10 or newer, with the `python` command on PATH.
3. Git for Windows.
4. Visual Studio 2022 Community or Build Tools with **Desktop development with
   C++** and **C++ CMake tools for Windows** selected.
5. At least 30 GB of free disk space; more is preferable for build files and
   keeping multiple models. The default weight download is 2.74 GB; 27B is 18.97 GB.

The setup script itself does not install Windows software and does not request
administrator privileges. Installing Visual Studio or Git may require the
computer owner's normal installation permissions.

## Build and download

Open **Developer PowerShell for VS 2022**, change to this folder, and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
python .\manage_models.py

# Or use explicit setup commands instead of the menu:
.\setup_qwen.ps1 -Preflight
.\setup_qwen.ps1

# Explicit model selection uses the same models.json as Linux
.\setup_qwen.ps1 -ModelPreset qwen3.5-4b

# Optional text-chat alternatives, sharing the same compiled runtime:
.\setup_qwen.ps1 -ModelPreset gemma4-e2b -ModelOnly
.\setup_qwen.ps1 -ModelPreset phi4-mini -ModelOnly
```

The execution-policy change applies only to that PowerShell process. You may
instead use your organization's approved script-signing policy.

Build or download separately:

```powershell
.\setup_qwen.ps1 -RuntimeOnly
.\setup_qwen.ps1 -ModelOnly
```

## Start the browser interface

```powershell
.\start_qwen.ps1
```

On the first run, `start_qwen.ps1` invokes setup automatically. Later runs go
directly to the local server. Use `-NoBrowser` or `-Port 18080` when needed.

```powershell
.\start_qwen.ps1 -ModelPreset qwen3.5-4b -Thinking off -Threads 8

# Ctrl+C first, then choose a different installed model:
.\start_qwen.ps1 -ModelPreset qwen3.8-27b -Thinking off

# Or select installed models in the browser, with one model loaded at a time:
.\start_qwen.ps1 -Router -Thinking off
```

With `-Context` omitted, the Python launcher prefers 64K and estimates memory
before starting, with 32K/16K/8K fallbacks. On the provided Windows CPU build this
uses available physical RAM, not GPU memory. Inspect without starting a model:

```powershell
python run_server.py --router --backend cpu --context-report
```

`-Context 65536` forces a value and bypasses automatic sizing. Real Windows
hardware probing and model startup remain untested; syntax support and mocked
tests are not end-to-end Windows validation.

To list presets: `python .\run_server.py --list-models`. Selecting
`qwen3-30b-a3b` explicitly downloads the old model if its weights are absent.
The setup verifies the pinned model SHA-256 before accepting its `.part` file.
Router mode lists installed catalog weights only and never downloads missing
models. Add weights explicitly with `setup_qwen.ps1 -ModelPreset NAME -ModelOnly`,
then restart the router. Windows router operation still needs an end-to-end test.
The runtime is built CPU-only; CUDA is not silently enabled. Runtime-native
HTTPS is disabled in this Windows build to avoid requiring an OpenSSL SDK;
model downloads still use HTTPS through Windows curl.

If the browser does not open, visit `http://127.0.0.1:8080` after the terminal
reports that the model is loaded. Keep PowerShell open; press `Ctrl+C` to stop.

## What it does not do

The local browser is a chat interface. It does not automatically receive file,
terminal, GitHub, or operating-system permissions.
