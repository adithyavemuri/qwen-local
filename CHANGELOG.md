# Changes

## Multi-model beta update — 2026-10-22

- Added selectable, pinned Qwen3.5-4B, Gemma 4 E2B and Phi-4-mini weights.
- Retained Qwen3.8-27B and Qwen3-30B-A3B catalog entries.
- Added a cross-platform terminal menu with explicit download consent, model
  notes, installed status, disk space and hardware cautions.
- Added native browser routing between installed models, with one model loaded
  at a time, offline mode and a project-local cache.
- Added optional rootless, checksum-pinned Linux Vulkan binaries; drivers and
  system libraries are not changed. CPU operation remains available.
- Pinned model sizes/hashes, runtime source commit, GPU archive and portable
  CMake archive. Upstream browser-asset provisioning remains an external dependency.
- Added offline regression tests, reusable real-model examples and Linux CI.
- Kept Windows x64 scripts and syntax checks; real Windows installation and
  runtime validation are explicitly deferred. Windows GPU setup is not provided.
- Kept the historical script names and QWEN_* variables for compatibility.

No autonomous agent framework, model collaboration controller, filesystem
tools or GitHub permissions are enabled by this update.
