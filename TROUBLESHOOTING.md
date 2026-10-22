# Troubleshooting

Keep the terminal open: setup and llama.cpp errors are printed there. Never
solve a missing prerequisite by blindly running an administrator command.

| Symptom | What to do |
| --- | --- |
| Python not found | Install Python 3.10+ through your approved process. Use `python3` on Linux or `python` on Windows. |
| Missing compiler/build command | Linux CPU builds require Git, a C++ compiler, make and tar. Windows requires Developer PowerShell with VS 2022 C++/CMake tools. Setup reports the missing command; it does not install system packages. |
| Download interrupted | Repeat the same setup command. The `.part` transfer resumes and must pass size/header/SHA-256 checks before acceptance. |
| SHA-256 mismatch | Stop using that file. It is not accepted or silently deleted. Check the publisher/revision and move the damaged file aside before downloading again. Do not disable verification. |
| Model absent from selector | It must have a catalog entry and a complete installed file. Run `python3 manage_models.py --list`, install explicitly, then restart router mode. |
| Port already in use | Stop your own existing server with Ctrl+C, or use `python3 run_server.py --router --port 18080`. Do not kill unrelated processes. |
| GPU runtime fails | Use `--backend cpu`. Optional Vulkan setup needs an existing compatible driver/loader. This project does not install or upgrade drivers. |
| Out of memory / slow generation | Choose smaller weights, reduce `--context`, close other workloads or force CPU. More CPU threads are not always faster. |
| Unsupported architecture/template | A GGUF file may require a newer runtime or a corrected conversion. Keep the working runtime intact while checking compatibility. |
| Windows execution policy blocks scripts | Use the process-only policy example in WINDOWS_GUIDE.md if permitted by your organization. Do not change machine-wide policy. |

Safe inspection commands:

```bash
python3 manage_models.py --list
python3 manage_models.py --install phi4-mini --dry-run
python3 run_server.py --list-models
./setup_qwen.sh --preflight
python3 model_config.py --preset phi4-mini --verify models/Phi-4-mini-instruct-Q4_K_M.gguf
```

`--dry-run` prints commands without downloads, compilation or model startup.
The explicit `--verify` command reads the full file and may take time.
On Windows substitute `python`, and use `setup_qwen.ps1 -Preflight`.

Optional real-model checks (weights/runtime must already be installed):

```bash
python3 examples/smoke_test.py --preset phi4-mini --backend cpu
python3 examples/smoke_test_router.py --models qwen3.5-4b gemma4-e2b phi4-mini qwen3.5-4b
```

These examples start their own localhost test servers and save reports/logs in
`logs/`. They do not download weights or prove general answer correctness.
