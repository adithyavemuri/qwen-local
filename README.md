# Standalone local Qwen

This folder builds a local `llama.cpp` runtime, downloads Qwen3-30B-A3B in GGUF
format, and starts a private browser chat. Linux and Windows x64 have separate
setup scripts. Generated files remain inside this folder.

## Quick start

Linux:

```bash
./start_qwen.sh
```

Windows, from Developer PowerShell for Visual Studio 2022:

```powershell
.\start_qwen.ps1
```

The start script checks for the runtime and model, runs setup when either is
missing, starts the local server, and opens the browser. The first run includes
an approximately 18.6 GB model download and therefore cannot be instant.

Run the explicit preflight first when diagnosing a new machine:

```bash
./setup_qwen.sh --preflight
```

```powershell
.\setup_qwen.ps1 -Preflight
```

See [WINDOWS_GUIDE.md](WINDOWS_GUIDE.md) for Windows prerequisites and
[BROWSER_GUIDE.md](BROWSER_GUIDE.md) for daily operation.

## How it works

1. Checks the platform-specific Git, CMake, compiler, download, and archive
   prerequisites.
2. Uses host CMake. Linux x86-64 can bootstrap portable CMake locally when it
   is missing; Windows uses Visual Studio's CMake/MSVC environment.
3. Clones a pinned `llama.cpp` revision into `build/`.
4. Compiles CPU versions of `llama-server` and `llama-cli` locally.
5. Downloads the official Qwen3-30B-A3B Q4_K_M GGUF into `models/`.
6. Leaves all generated files under `qwen-local/`.

The neural-network model itself is already trained; it is downloaded, not
compiled. `llama.cpp` is the inference program that is compiled.

## Hardware and storage warning

The default model download is approximately 18.6 GB. Allow additional space
for the `llama.cpp` source and build directory. CPU inference works but can be
slow. Available CPU threads are used by default; this does not limit the model
to one core.

## Linux installation

```bash
cd qwen-local
./setup_qwen.sh --preflight
./setup_qwen.sh
```

Build only the runtime or download only the model:

```bash
./setup_qwen.sh --runtime-only
./setup_qwen.sh --model-only
```

The download is resumable. The script never invokes a system package manager.
If a required host command is missing, it stops and reports it.

## Run and use in a browser

```bash
python3 run_server.py
```

Wait until the terminal reports that the model is loaded, then open:

```text
http://127.0.0.1:8080
```

`llama-server` supplies its own browser chat interface. Keep the terminal open.
Press `Ctrl+C` to stop it.

For a short operator-oriented version, see `BROWSER_GUIDE.md`.

To open the browser automatically:

```bash
python3 run_server.py --open-browser
```

To inspect the command without starting the model:

```bash
python3 run_server.py --dry-run
```

## Useful options

```bash
python3 run_server.py --threads 16 --context 8192 --port 8080
```

CPU-only operation is the safe default. If you deliberately build a compatible
GPU backend, `--gpu-layers` can request offload. GPU support is hardware- and
toolchain-specific and is not automatically configured by this package.

## Security boundary

The launcher binds to `127.0.0.1`, so it is available only on this computer. Do
not change the host to `0.0.0.0` unless you understand the network exposure and
add appropriate authentication. This launcher does not enable filesystem tools
or connect Qwen to another program.

See `LIMITATIONS.md` for the complete supported boundary.

## Repository contents

- `setup_qwen.sh`: Linux setup
- `setup_qwen.ps1`: Windows x64 setup
- `start_qwen.sh`: one-command Linux setup/start
- `start_qwen.ps1`: one-command Windows setup/start
- `run_server.py`: cross-platform server launcher
- `BROWSER_GUIDE.md`: normal browser use
- `WINDOWS_GUIDE.md`: Windows prerequisites and setup
- `LIMITATIONS.md`: honest support boundary
- `RELEASE_CHECKLIST.md`: checks before publishing

The ignored `models/`, `runtime/`, `downloads/`, and `build/` directories are
created locally and must not be uploaded to GitHub.

## Upstream sources

- llama.cpp: https://github.com/ggml-org/llama.cpp
- Qwen model: https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF
