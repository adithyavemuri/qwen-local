# Current limitations

- The default Qwen GGUF download is approximately 18.6 GB.
- CPU inference can be slow even though the launcher uses multiple threads.
- Runtime compilation supports Linux x86-64 and has a Windows x64 PowerShell
  path. The Windows path still needs an end-to-end clean-machine test.
- Windows requires Visual Studio 2022 C++/CMake tools, Git, curl, and Python to
  be installed before running the setup script.
- GPU acceleration is not automatically configured.
- The setup depends on upstream GitHub and Hugging Face availability.
- Downloads use HTTPS but are not currently checked against pinned SHA-256
  values.
- The `llama.cpp` revision is pinned, but the portable CMake and model URLs are
  external dependencies that may eventually change.
- The browser binds locally and provides chat only. It cannot inspect files,
  execute code, maintain GitHub, or call the WRF package.
- A language model response is not evidence of correctness and must not replace
  deterministic source inspection or scientific validation.
