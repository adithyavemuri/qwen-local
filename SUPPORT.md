# Platform and feature status

| Platform/feature | Status |
| --- | --- |
| Linux x86-64 CPU build and chat | Locally verified with GNU 11.4 / Python 3.10 |
| Linux x86-64 portable Vulkan | Locally verified on an NVIDIA Ada GPU using an existing driver |
| Intel/AMD Vulkan GPUs | Runtime may support them; not locally validated here |
| Windows 10/11 x64 CPU scripts | Compatibility implemented; end-to-end testing deferred |
| Windows GPU setup | Not provided |
| macOS / ARM / other architectures | Not supported by this setup workflow |
| Python 3.10+ | Standard library only; Linux CI checks 3.10 and 3.13 |

Linux CI runs offline tests and entry-point checks. Windows CI parses PowerShell
and Python syntax only. Neither job downloads multi-GB weights, compiles the
inference engine or validates model responses. Real installed-model tests are
separate examples, not claims of general model correctness.

The launcher supports text-chat GGUF models whose architecture, tokenizer and
chat template are supported by the pinned llama.cpp runtime. A valid GGUF
extension alone does not establish compatibility. See [MODEL_GUIDE.md](MODEL_GUIDE.md).

No root commands, system package installation, driver upgrades, model file
deletion or remote publication are performed by setup. Model downloads require
network access; local chat can run offline after installation. Existing host
build tools and GPU drivers are the user's prerequisites.

The server binds to localhost. This is not authentication or an operating-system
sandbox. Do not expose the server publicly. Agent mode and UI MCP proxy are
disabled; this project does not grant models shell, GitHub or WRF access.

Windows is explicitly a compatibility path, not a tested-platform guarantee.
