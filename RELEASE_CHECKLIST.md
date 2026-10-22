# GitHub release checklist

- [x] Linux setup and launcher are documented.
- [x] Windows x64 PowerShell setup and launcher are documented.
- [x] Model files, compiled runtimes, build trees, and downloads are ignored.
- [x] Default server binding is localhost only.
- [x] Setup scripts avoid administrator commands and system package managers.
- [x] MIT license is present for the scripts and documentation.
- [x] Document separate launcher/runtime/model licenses and upstream source links.
- [ ] Deferred: test Windows setup, model loading and browser switching end to end.
- [x] Built-in model downloads use pinned revisions, sizes and SHA-256.
- [x] Pin portable CMake size/SHA-256 and verify the archive before extraction.
- [x] Model selection is shared across Linux, Windows and Python launchers.
- [x] Add offline selection, integrity and launcher regression tests.
- [x] Complete a real Qwen3.8-27B load, browser and generation smoke test.
- [x] Complete a real Qwen3.5-4B load, browser and generation smoke test.
- [x] Test the pinned Linux Vulkan runtime on an existing NVIDIA GPU without driver changes.
- [x] Record a longer Qwen3.5-4B GPU reply with server-reported decode timing.
- [x] Document model switching, installed-weight reuse and explicit CPU fallback.
- [x] Test native browser router API switching 4B → 27B → 4B with one active model.
- [x] Test missing-model rejection and document explicit downloads outside router mode.
- [x] Verify Gemma 4 E2B and Phi-4-mini GGUF downloads, browser serving and generation.
- [x] Test Qwen → Gemma → Phi → Qwen routing with one active model at a time.
- [x] Confirm that no model weights or compiled binaries are staged in Git.
- [x] Provide a model menu, download consent, installed status and disk/memory caveats.
- [x] Configure offline regressions in Linux CI; label Windows checks as syntax-only.
- [x] Document unsupported features and actionable troubleshooting steps.

