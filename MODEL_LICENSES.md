# Licenses and upstream sources

The scripts/documentation in this repository are [MIT licensed](LICENSE).
That does not relicense model weights, third-party programs or their dependencies.
Weights and compiled runtimes are downloaded locally and excluded from Git.

| Component/model | Published license | Source |
| --- | --- | --- |
| llama.cpp | MIT | [Source and license](https://github.com/ggml-org/llama.cpp) |
| Portable CMake | BSD-3-Clause (with bundled third-party notices) | [CMake licensing](https://cmake.org/licensing/) |
| Qwen3.5-4B | Apache-2.0 | [Original model](https://huggingface.co/Qwen/Qwen3.5-4B) |
| Gemma 4 E2B IT | Apache-2.0 | [Original model](https://huggingface.co/google/gemma-4-E2B-it) |
| Phi-4-mini-instruct | MIT | [Original model](https://huggingface.co/microsoft/Phi-4-mini-instruct) |
| Qwen3.8-27B | Apache-2.0 | [Original model](https://huggingface.co/Qwen/Qwen3.8-27B) |
| Qwen3-30B-A3B | Apache-2.0 | [Original model](https://huggingface.co/Qwen/Qwen3-30B-A3B) |

`models.json` records the GGUF publisher, immutable revision, filename, size,
checksum and original model link. The original developer and GGUF publisher
may differ. Read the original and conversion repository notices before use
or redistribution, preserve applicable notices, and check any derivative
model separately. This table is a source index, not a legal assessment.

The optional GPU archive is an official llama.cpp binary release, verified
against its pinned archive hash. Existing system Vulkan drivers are used but
not redistributed, installed or modified by this project.
