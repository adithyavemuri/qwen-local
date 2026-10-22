# Current limitations

- Automatic context sizing is an estimate from model metadata and a snapshot
  of available RAM/GPU memory, not a real allocation test. It prefers 64K,
  then 32K/16K/8K, and reports per-model choices. Compute/recurrent allowances and
  headroom are heuristics. Gemma sliding-window caches are conservatively
  charged at full context; unrecognized architectures require a manual override.
  Read [CONTEXT_SIZING.md](CONTEXT_SIZING.md) before interpreting a fit report.
  CPU/partial offload can use RAM but is not equivalent to fast full-GPU inference.
  Explicit `--context` bypasses the automatic check. The launcher does not resize
  an existing server, edit IDE settings, or silently retry an OOM failure.

- The default Qwen3.5-4B Q4_K_M GGUF download is 2.74 GB; the optional 27B is
  18.97 GB. Runtime buffers and
  the selected context/cache require additional RAM.
- CPU inference can be slow even though the launcher uses multiple threads.
- Runtime compilation supports Linux x86-64 and has a Windows x64 PowerShell
  path. The Windows path still needs an end-to-end clean-machine test.
- Windows requires Visual Studio 2022 C++/CMake tools, Git, curl, and Python to
  be installed before running the setup script.
- Optional `setup_gpu.py` installs pinned portable Vulkan binaries on Linux
  x86-64 only. An existing compatible Vulkan GPU driver/loader and Ubuntu-compatible
  system libraries are required. It does not install or upgrade drivers.
  Windows GPU setup is not provided. Without this optional setup, launch is CPU-only.
- Single-model mode switches with a stop/start. Optional `--router` enables
  browser selection, unloading/reloading weights and allowing one model instance
  at a time. Switching takes time and does not transfer internal context/KV state.
- Router mode lists only complete installed catalog models, not arbitrary GGUFs
  or the user's global model cache. It is offline and does not download missing
  models. Restart after explicit setup/download to refresh the generated list.
  Custom QWEN_MODEL_FILE/URL overrides are unsupported in router mode.
- The setup depends on upstream GitHub and Hugging Face availability.
- Built-in model downloads pin revision, size and SHA-256. Custom model
  overrides are only checksum-verified if the user supplies the checksum.
- Runtime source is pinned to llama.cpp v0.7.0 and its full commit. Portable
  CMake and upstream prebuilt browser-UI assets are external dependencies;
  portable CMake is size/SHA-256-pinned, while upstream UI provisioning may
  fall back to its latest assets. The entire toolchain is not bit-reproducible.
- The current launcher configures text chat only. Native model vision/video
  capability does not mean that the required projector is installed/enabled.
- CPU-native binaries are optimized for the build machine and are not
  guaranteed portable to older CPUs. Rebuild on the target machine.
- Startup checks size, not a full re-hash of the weights on every launch. Run setup
  or model_config.py --verify again when you need to recheck file integrity.
- The browser binds locally and provides chat only. It cannot inspect files,
  execute code, maintain GitHub, or call the WRF package.
- A language model response is not evidence of correctness and must not replace
  deterministic source inspection or scientific validation.
- This is a GitHub scripts project, not a pip-installable distribution or a
  universal model manager. New catalog entries require compatible GGUFs and
  explicit source/hash metadata. Hardware guidance is not an automatic benchmark.
