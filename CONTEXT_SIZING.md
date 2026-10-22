# How automatic context sizing works

The preferred default is **32,768 tokens**, not 4K. With no `--context` argument,
the launcher reads the installed model's GGUF header and checks available memory
before starting. There are no new Python dependencies, downloads or driver
changes in this check. Model weights are not loaded for the estimate.

```bash
python3 run_server.py --router --context-report   # inspect only
./start_qwen.sh --router --thinking off           # size automatically and start
./start_qwen.sh --router --context 65536          # manual override, not a fit check
```

The default policy tries **32K → 16K → 8K**. It never chooses a larger window
than the model's recorded trained context. If even 8K cannot be established
within the RAM budget, that model is unavailable in automatic mode. A failed
startup-model plan stops the launch with an explanation; a failed plan for a
different installed model omits that model from the generated router config.
No model is downloaded or deleted by this decision.

## The formula

For one sequence and FP16 key/value caches:

```text
KV bytes = sum over cache-owning attention layers of:
           context_tokens × KV_heads × (key_head_dimension + value_head_dimension)
           × 2 bytes per FP16 value

Simple equal-dimension case:
KV bytes = 2 × tokens × attention_layers × KV_heads × head_dimension × 2 bytes
```

The first `2` in the simple expression represents key and value tensors. It is
not the quantization of the model weights. Q4 model weights do not imply Q4 KV
cache. The launcher uses llama.cpp's normal FP16 cache assumption.

Supported metadata paths cover the bundled Qwen35, Qwen3/Qwen3MoE, Gemma4 and
Phi3-architecture weights, plus ordinary Llama/Qwen2 caches. Dimensions come
from the actual installed file, not parameter-count guesses or preset names.
Unknown architectures are not assumed equivalent: automatic estimation fails
clearly, and an explicit `--context N` remains available for expert use.

- Qwen35: only full-attention blocks get a context-growing KV cache. Recurrent
  blocks are identified by their explicit mask or full-attention interval.
  A separate heuristic recurrent allowance is included; it is not an exact
  recurrent-state allocation calculation. Speculative MTP is not enabled.
- Phi: ordinary per-layer attention KV is counted. No savings are assumed from
  sliding windows that the pinned runtime does not use for this architecture.
- Gemma4: shared KV layers are counted only once. Sliding-window layers are
  conservatively charged at full context and the larger head dimension. This
  can choose a smaller context than the runtime could actually support.

For illustration, Qwen3.5-4B's eight full-attention blocks, four KV heads and
256-dimensional keys/values give 1 GiB at 32K. Phi Mini's 32 blocks, eight KV
heads and 128-dimensional keys/values give 4 GiB at 32K. These are analytical
cache estimates, not measured total VRAM use or speed benchmarks.

## Weight, buffer and safety allowances

The planner uses the GGUF file size as a conservative weight-memory proxy.
Its estimate is:

```text
estimated allocation = weights + KV + 10% of (weights + KV) + fixed allowance
fixed allowance      = max(768 MiB, 10% of weights)
                       + 256 MiB for Qwen35 recurrent/compute state
RAM reserve          = max(2 GiB, 10% of currently available RAM)
GPU reserve          = max(512 MiB, 10% of selected GPU total memory)
```

All margins are **heuristics**, not model-theory results or guarantees. Actual
allocation depends on batch sizes, backend kernels, alignment, cache behavior,
lazy tensors and other processes. Reading file size is not tensor-by-tensor
memory accounting. This does not predict response quality or tokens/second.

Linux uses `MemAvailable`, accounting for the standard cgroup-v2 root memory
limit when present. Windows uses the standard available-physical-memory API;
Windows hardware execution is untested. CPU mode checks RAM. The installed GPU
runtime's read-only `--list-devices` report supplies the selected device's free
memory. Devices are not summed, and unknown or multi-device layouts are not
claimed to have a known GPU budget. A GPU probe failure chooses a conservative
16K-or-lower RAM-fitting plan and explicitly reports unknown GPU fit.

The planner first prefers a candidate whose entire estimated allocation fits
the GPU and RAM budgets. If weights are already too large for full GPU residency,
it checks RAM instead and reports **partial GPU offload expected**. This is not
a full-GPU fit guarantee: llama.cpp must still fit/offload its actual tensors.
When no full-GPU candidate fits otherwise, the smallest RAM-fitting candidate
is used with an explicit GPU-fit warning. No drivers, system configuration,
cache quantization or offload settings are changed by the estimator.

## Router, IDE and current processes

Every installed router model is planned independently, and only one instance
is loaded at a time. For example, Qwen might receive 32K while Phi receives 8K.
The chosen values are printed and written into the generated local router INI.
Startup sizing is a snapshot; it is not a continuous monitor when models switch.
An explicit `--context` forces that value for all router models and bypasses
the estimator. It does not guarantee that value fits or is scientifically useful.

**Stop the old server first.** Its allocated GPU memory is still in use during
a preflight and is not assumed reclaimable. The launcher never kills it for you.
Neither a YAML edit nor reloading VS Code changes an existing model allocation.

Continue's `contextLength` must match each model's printed context; the launcher
does not rewrite IDE files or read GitHub secrets. If a model falls back below
32K, lower only that model's `contextLength` in your Continue YAML before using
it and start a new conversation. Other clients may discover the server's actual
context automatically, but do not assume they all do.

`--dry-run` remains side-effect-free and skips hardware probing; it prints the
preferred setting, not a measured fit. `--context-report` performs only the
read-only estimate using installed files and an existing runtime. It does not
bootstrap a runtime, load weights, write an INI, start a server or test answers.
An estimated fit is not an actual successful 32K inference test. Startup failures
remain visible; there is no hidden retry or claim of success after an OOM.

## Primary sources and verification

- [llama.cpp cache allocation](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/src/llama-kv-cache.cpp)
- [Qwen35 recurrent/full-attention handling](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/src/models/qwen35.cpp)
- [Gemma4 shared-cache handling](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/src/models/gemma4.cpp)
- [Pinned runtime arguments and cache types](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/tools/server/README.md)
- [GGUF format](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)

Offline tests check the formulas against analytical results, fallback budgets,
unknown architectures/memory, malformed/truncated GGUF headers, individual
router contexts, manual overrides and no-start/no-write report behavior.
They do not certify actual GPU allocations or Windows model execution.
