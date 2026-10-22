# Run local models in a browser

## First-time setup on Linux

From this directory:

```bash
python3 manage_models.py
```

Choose a model number, install its weights, then launch it. Choose **B** after
installation to use browser model switching. The menu asks before downloading
missing weights and does not install system prerequisites or drivers.

For explicit script-based setup instead:

```bash
./setup_qwen.sh --preflight
./setup_qwen.sh
```

The first command only checks the host. The second compiles `llama.cpp` locally
and downloads the model. It does not use `sudo`.

On Windows, follow `WINDOWS_GUIDE.md`.

## Start the server

Fastest Linux path, including first-time setup when required:

```bash
./start_qwen.sh
```

Fastest Windows path from Developer PowerShell:

```powershell
.\start_qwen.ps1
```

Manual launcher commands are below.

Linux: `python3 run_server.py --open-browser`

Windows: `python .\run_server.py --open-browser`

If the browser does not open automatically, wait for the model-loaded message
and visit:

```text
http://127.0.0.1:8080
```

Keep the terminal open while chatting. Press `Ctrl+C` in that terminal to stop
the server.

## Choose models without restarting the server

Stop your current server once with Ctrl+C. Start router mode:

```bash
./start_qwen.sh --router --thinking off
```

Windows: `.\start_qwen.ps1 -Router -Thinking off`.

Open or refresh `http://127.0.0.1:8080`. In a new chat, use the model selector
to choose an installed model (Qwen, Gemma or Phi). The default Qwen 4B loads first. When a request selects
another model, the previous model unloads; only one instance is kept in memory.
Expect loading delays, especially for 27B. Your drivers are not changed.

Missing models are not listed or downloaded by the router. For example, to add
the 30B again, explicitly run this setup command, then restart router mode:

```bash
./setup_qwen.sh --model qwen3-30b-a3b --model-only
```

Router mode is offline and uses only complete catalog weights under `models/`.
Start a new chat for an independent comparison; switching models does not
transfer their internal context/KV cache. Browser chat history is separate.

To add the lightweight Gemma/Phi presets, explicitly download them and restart
router mode. Existing Qwen weights and the shared runtime are reused:

```bash
./setup_qwen.sh --model gemma4-e2b --model-only
./setup_qwen.sh --model phi4-mini --model-only
```

The selector is not an automatic team of agents. Models can be called sequentially
through the same `/v1/chat/completions` API, with the preset key as `model`.

## Common adjustments

Qwen3.5-4B Q4_K_M is the default; its first download is about 2.74 GB. The larger
27B preset remains selectable. The server uses one slot and prefers a 32,768-token
context, with automatic memory-based 16K/8K fallbacks. Thinking follows the model's
own default unless you select `--thinking` explicitly.

To force 32K for every installed model instead of automatic sizing, stop the
existing server and start it with an explicit override:

```bash
./start_qwen.sh --router --context 32768 --thinking off
```

`--context` overrides each generated router preset, not only the parent server,
and bypasses automatic context sizing. Without it, startup checks each installed
model separately using the [documented estimate](CONTEXT_SIZING.md). Match the
context setting in any connected IDE client to the running server. A larger
window consumes more memory and may reduce speed; 32K performance is not
verified for every catalog model on every machine.

Run `python3 run_server.py --router --context-report` for a read-only estimate
without loading models or changing your current server. Stop an old model
server before the actual new launch: its GPU allocation reduces available
memory and can affect the estimate. Restarting VS Code alone does not restart
the model server.

```bash
# Use a specific number of CPU threads
python3 run_server.py --threads 16

# Use another local-only port
python3 run_server.py --port 18080 --open-browser

# Print the command without loading the model
python3 run_server.py --dry-run

# List presets without loading or downloading anything
python3 run_server.py --list-models

# Start the compact model with direct answers
./start_qwen.sh --preset qwen3.5-4b --thinking off

# Stop with Ctrl+C before switching to another installed model
./start_qwen.sh --preset qwen3.8-27b --thinking off --threads 8

# Deliberately install/start the legacy model again
./start_qwen.sh --preset qwen3-30b-a3b
```

The default host is `127.0.0.1`, so other machines cannot connect. This browser
chat has no access to files, GitHub, terminals, or WRF tools. Such access would
require a separate, security-reviewed tool controller.

Windows model/direct-answer selection:

```powershell
.\start_qwen.ps1 -ModelPreset qwen3.5-4b -Thinking off -Threads 8
```

An old model may have been manually removed to free disk space. Choosing its
preset downloads it again; it does not silently use another installed model.

For GPU acceleration on Linux x86-64, run `python3 setup_gpu.py` once.
Afterwards `--backend auto` uses the installed GPU runtime; `--backend cpu`
forces CPU and `--backend vulkan` requires the GPU runtime. Setup needs an existing
compatible Vulkan GPU driver/loader but no administrator privileges or SDK.
No drivers or system libraries are installed, replaced or upgraded.
Single-model commands switch with a stop/start. `--router` lets you choose in
the browser, but switching still requires loading weights, not an instant swap.
