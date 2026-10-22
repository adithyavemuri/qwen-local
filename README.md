# Local models: Qwen, Gemma and Phi

[![checks](https://github.com/adithyavemuri/qwen-local/actions/workflows/checks.yml/badge.svg)](https://github.com/adithyavemuri/qwen-local/actions/workflows/checks.yml)

**Beta:** Linux operation is locally verified. Windows x64 compatibility is
implemented, but installation, model loading and browser switching have not
been validated end to end on Windows. See [support status](SUPPORT.md).

This folder builds a pinned local `llama.cpp` runtime, downloads a selected model
GGUF, and starts a private browser chat. **Qwen3.5-4B Q4_K_M is the default.**
Linux and Windows x64 use the same model catalog and Python launcher.
Generated files remain inside this folder; no root access is used.

Already have models installed? Use `./start_qwen.sh --router --thinking off`
to switch between them in the browser without restarting the server.

## Quick start

Clone the repository. Python 3.10+ is required; no Python dependencies need to
be installed with pip. This is a scripts-based GitHub project, not a PyPI package.

```bash
git clone https://github.com/adithyavemuri/qwen-local.git
cd qwen-local
python3 manage_models.py
```

Windows, from Developer PowerShell for Visual Studio 2022:

```powershell
git clone https://github.com/adithyavemuri/qwen-local.git
cd qwen-local
python manage_models.py
```

The menu shows model download sizes, installed status, free disk space and
model-specific cautions. Choose a number, then install or launch it. Missing
weights require confirmation; nothing downloads just by opening the menu.
After installing models, choose **B** for browser model switching.

First-time compilation needs Git, a C++ compiler and build tools on Linux, or
Visual Studio C++/CMake tools on Windows. The menu does not install those system
prerequisites. See [Windows setup](WINDOWS_GUIDE.md) and
[troubleshooting](TROUBLESHOOTING.md).

Non-interactive examples (use `python` instead of `python3` on Windows):

```bash
python3 manage_models.py --list
python3 manage_models.py --install gemma4-e2b
python3 manage_models.py --install phi4-mini --dry-run
python3 manage_models.py --start phi4-mini
python3 manage_models.py --browser
```

`--yes` confirms an explicitly selected model download for automation. The
existing `start_qwen.sh` / `start_qwen.ps1` entry points remain available.

## Choose a model

`models.json` is the readable, shared catalog. It pins each download revision,
file size and SHA-256, and the runtime source revision/commit. Read
[model licenses](MODEL_LICENSES.md) before using or redistributing weights.

| Preset | Model | Weight download |
| --- | --- | --- |
| `qwen3.5-4b` (default) | Qwen3.5-4B, Q4_K_M from Unsloth | 2.74 GB |
| `gemma4-e2b` | Google Gemma 4 E2B IT, Q4_0 from ggml-org | 2.84 GB |
| `phi4-mini` | Microsoft Phi-4-mini-instruct, Q4_K_M from Unsloth | 2.49 GB |
| `qwen3.8-27b` | Qwen3.8-27B, dense, Q4_K_M from ggml-org | 18.97 GB |
| `qwen3-30b-a3b` | Previous Qwen3-30B-A3B MoE, Q4_K_M from Qwen | 18.56 GB |

Only the selected model is downloaded. Preset availability does not mean its
weights are installed. Neither setup nor the launcher deletes other weights.

The `qwen-local` folder, script names and `QWEN_*` environment variables are
retained for compatibility; model selection is shared across all catalog families.
GGUF conversions are published by the organizations listed above, not necessarily
the original model developers. Model licenses are separate from this launcher's
license. Gemma and Phi presets enable text chat only; no vision/audio projector
is downloaded and no new tools or filesystem permissions are granted.

```bash
# Explicitly add another model without rebuilding the existing runtime:
./setup_qwen.sh --model gemma4-e2b --model-only
./setup_qwen.sh --model phi4-mini --model-only
# Then restart router mode to show all complete installed models:
./start_qwen.sh --router --thinking off
```

### Switch models inside the browser

Stop the current single-model server with Ctrl+C, then start router mode:

```bash
./start_qwen.sh --router --thinking off
```

Windows: `.\start_qwen.ps1 -Router -Thinking off`.

Open `http://127.0.0.1:8080`, start a chat and choose a model from the browser's
model selector. Only complete, installed catalog weights are listed. The default
model loads first; choosing another model for a request unloads the previous
one. Only **one model instance** is allowed at a time, to limit RAM/VRAM usage.
The same browser URL stays open. Allow time for weight loading; switching to a
27B model will not make it as fast as the 4B model.

Router mode is offline: it does not download missing weights. To add the missing
30B preset, explicitly download it, then restart the router to refresh its list:

```bash
./setup_qwen.sh --model qwen3-30b-a3b --model-only
./start_qwen.sh --router --thinking off
```

Use `--router --preset qwen3.8-27b` to change the initially loaded model, or
`--router --backend cpu` to use CPU. Without `--router`, the original single-model
commands below still work. Router mode uses the native llama.cpp web UI and
model manager, not a separate web application. Each model has its own runtime
context: chat text may be sent by the browser, but internal model state/KV cache
is not transferred. Start a new chat for clean model comparisons.

```bash
python3 run_server.py --list-models
./setup_qwen.sh --model qwen3.5-4b
./start_qwen.sh --preset qwen3.5-4b --thinking off

# To switch: Ctrl+C, then start the other preset. Installed weights are reused.
./start_qwen.sh --preset qwen3.8-27b --thinking off
```

Windows equivalents:

```powershell
python .\run_server.py --list-models
.\setup_qwen.ps1 -ModelPreset qwen3.5-4b
.\start_qwen.ps1 -ModelPreset qwen3.5-4b
```

The start scripts rebuild a missing or outdated runtime and download missing
selected weights. A partial `.part` download is never treated as an installed
model. Setup checks size, GGUF header and the full SHA-256 before renaming it.
An existing final file is verified and reused; an invalid one is not overwritten.

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
5. Downloads the selected, revision-pinned GGUF into `models/` and checks SHA-256.
6. Leaves all generated files under `qwen-local/`.

The browser selector routes each request to one selected model. It does not
make the models collaborate, merge their weights, or make them validate each
other automatically. A separate controller can call `/v1/chat/completions`
sequentially, passing a draft from one model as input to another. That adds
loading/inference time and can propagate errors; agreement is not proof.

The neural-network model itself is already trained; it is downloaded, not
compiled. `llama.cpp` is the inference program that is compiled.

## Hardware and storage warning

The default model download is approximately 2.74 GB. Allow additional space
for the `llama.cpp` source and build directory. CPU inference works but can be
slow. Up to eight CPU threads are used by default; adjust `--threads` to measure
what works best on your machine. Qwen3.8-27B is dense and can be considerably slower than the old
MoE; model parameter count alone does not predict speed. Enough RAM to load
weights does not guarantee a fast response. Context/cache and runtime buffers
need additional memory. The preferred default is **65,536 context tokens** with
one slot. Startup estimates memory from the actual GGUF metadata and available
RAM/selected GPU memory, falling back to 32K, 16K or 8K when appropriate. A partial
GPU-offload estimate is clearly distinguished from a full GPU fit; this is not
an allocation guarantee. See [context sizing](CONTEXT_SIZING.md).

```bash
# Read-only estimate for installed models; no downloads or model loading:
python3 run_server.py --router --context-report

# Automatic sizing is enabled when --context is omitted:
./start_qwen.sh --router --thinking off

# An explicit value bypasses automatic sizing (you accept memory-fit risk):
./start_qwen.sh --router --context 65536 --thinking off
```

In router mode each model may receive a different context. Match a connected
IDE's context setting to that model's startup report; changing an IDE YAML
does not resize an already-running server. Stop the old server first.

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

# Direct answers rather than lengthy reasoning (model/template dependent)
python3 run_server.py --thinking off --threads 8

# A different existing compatible GGUF; no automatic download for this path
python3 run_server.py --model /path/to/model.gguf
```

## Optional rootless GPU acceleration (Linux x86-64)

An existing compatible Vulkan GPU driver/loader is required. No SDK,
administrator privileges or system package installation is needed. The installer
does not install, replace or upgrade drivers or system libraries:

```bash
python3 setup_gpu.py
./start_qwen.sh --preset qwen3.5-4b --backend vulkan --thinking off
```

This downloads approximately 30 MB of official Vulkan binaries/libraries,
pins the release and archive SHA-256, checks the runtime commit and
GPU visibility, and installs under `runtime/vulkan/`. The locally compiled CPU
runtime is kept. These optional GPU binaries are downloaded, not compiled here.
Platform/driver compatibility is checked before the installation is accepted.
On hybrid laptops the installer prefers an NVIDIA device over integrated Intel
graphics. Use `--device Vulkan0` (or another name reported by `--list-devices`
on the runtime) to override the saved choice. Device numbering is machine-specific;
the saved choice may need updating after hardware changes.

`--backend auto` (default) uses this installed Vulkan runtime, otherwise CPU.
Use `--backend cpu` to force CPU or `--backend vulkan` to require Vulkan. Vulkan uses
automatic layer fitting unless `--gpu-layers N` is supplied; fit/speed depends
on free VRAM, model and context. Windows setup still builds CPU-only.

Single-model mode switches with a stop/start. Router mode switches in the browser
without restarting the main server, but still unloads/reloads model weights.
Neither mode is an instant hot swap or transfers internal model state. No weight
download or recompilation is needed to switch between already installed presets.
For an editable, short example, see [examples/chat.sh](examples/chat.sh).

`--thinking auto` preserves the model's default, `on` enables thinking, and
`off` requests direct answers through llama.cpp's `--reasoning` option. This is not
a guarantee about answer length or correctness. Vision input is not configured:
it needs a matching projector plus explicit launcher/runtime support. This
upgrade is tested as text chat, not image/video understanding.

Advanced overrides remain available: `QWEN_MODEL_PRESET`, `LLAMA_CPP_REF`, and a
custom pair `QWEN_MODEL_FILE`/`QWEN_MODEL_URL`. For custom downloads, provide
`QWEN_MODEL_SHA256` and `QWEN_MODEL_SIZE` too; without them setup warns that
integrity verification is weaker. Explicit `--preset` overrides the preset
environment variable. Compatibility of arbitrary models/runtime overrides is
the user's responsibility.

## Security boundary

The launcher binds to `127.0.0.1`, so it is available only on this computer. Do
not change the host to `0.0.0.0` unless you understand the network exposure and
add appropriate authentication. This launcher does not enable filesystem tools
or connect Qwen to another program.

The launcher explicitly disables the runtime's agent mode and UI MCP proxy,
and restricts browser CORS origins to localhost. These are not authentication
or an OS sandbox: do not expose this server as a public service.

See `LIMITATIONS.md` for the complete supported boundary.

## Repository contents

- `setup_qwen.sh`: Linux setup
- `manage_models.py`: cross-platform model menu and install/start commands
- `setup_qwen.ps1`: Windows x64 setup
- `start_qwen.sh`: one-command Linux setup/start
- `start_qwen.ps1`: one-command Windows setup/start
- `run_server.py`: cross-platform server launcher
- `setup_gpu.py`: optional, checksum-pinned Linux Vulkan runtime installer
- `models.json` / `model_config.py`: shared model pins, selection and verification
- `model_router.py`: installed-only, offline browser routing configuration
- `tests/test_local_qwen.py`: offline configuration and launcher regression tests
- `BROWSER_GUIDE.md`: normal browser use
- `WINDOWS_GUIDE.md`: Windows prerequisites and setup
- `LIMITATIONS.md`: honest support boundary
- `MODEL_GUIDE.md`: choosing models, custom GGUFs and extending the catalog
- `MODEL_LICENSES.md`: model/runtime licenses and upstream sources
- `SUPPORT.md` / `TROUBLESHOOTING.md`: platform status and actionable errors
- `RELEASE_CHECKLIST.md`: checks before publishing

The ignored `models/`, `runtime/`, `downloads/`, and `build/` directories are
created locally and must not be uploaded to GitHub.

## Upstream sources

- llama.cpp: https://github.com/ggml-org/llama.cpp
- Default original model: https://huggingface.co/Qwen/Qwen3.5-4B
- Default GGUF (third-party conversion): https://huggingface.co/unsloth/Qwen3.5-4B-GGUF
- Large-model GGUF: https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF
- Gemma original: https://huggingface.co/google/gemma-4-E2B-it
- Gemma GGUF: https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF
- Phi original: https://huggingface.co/microsoft/Phi-4-mini-instruct
- Phi GGUF: https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF
- Legacy GGUF: https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF

## Offline tests

```bash
python3 -m unittest discover -s tests -v
```

These do not download/load models or prove response quality. A real model-load
and HTTP generation check is separate:

```bash
python3 examples/smoke_test.py --preset qwen3.5-4b --backend cpu
python3 examples/smoke_test.py --preset qwen3.5-4b --backend vulkan --benchmark

# Requires both the 4B and 27B weights already installed; no downloads
python3 examples/smoke_test_router.py --backend vulkan
```

Results and server logs are saved in `logs/`, separately for each model/backend.
The optional benchmark records a longer reply and server timing fields; exact
two-word replies alone are not a sustained speed benchmark.

The benchmark is not a code-quality test: generated explanations/code can contain
errors even when installation checks pass. Review and test real coding changes.

It starts a temporary CPU server on localhost, checks the browser HTML, requests
two short replies, saves logs/JSON under `logs/`, and stops its own server. This
is not an interactive browser test or a scientific accuracy benchmark.
Windows end-to-end verification must be
performed on a Windows x64 machine; Linux tests do not certify Windows builds.

## License

The setup and launcher code in this repository is released under the
[MIT License](LICENSE). Downloaded models and llama.cpp remain subject to their
respective upstream licenses.
