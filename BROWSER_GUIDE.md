# Run Qwen in a local browser

## First-time setup on Linux

From this directory:

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

## Common adjustments

```bash
# Use a specific number of CPU threads
python3 run_server.py --threads 16

# Use another local-only port
python3 run_server.py --port 18080 --open-browser

# Print the command without loading the model
python3 run_server.py --dry-run
```

The default host is `127.0.0.1`, so other machines cannot connect. This browser
chat has no access to files, GitHub, terminals, or WRF tools. Such access would
require a separate, security-reviewed tool controller.
