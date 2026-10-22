# Choosing and adding models

## Start small

Open `python3 manage_models.py` (`python manage_models.py` on Windows).

1. Choose a model number to see its intended use and memory caveat.
2. Choose install. Read the publisher, size and license link, then confirm.
3. Choose launch, or return and choose B for browser model switching.

Qwen3.5-4B is the compact general default. Gemma 4 E2B and Phi-4-mini are compact
alternatives. The 27B and 30B models need much more storage and memory; sufficient
RAM does not make them fast. Runtime/cache memory is additional to the listed
weight size. GPU fit depends on free VRAM, context and quantization. Start with
the automatic context preflight (64K preferred, 32K/16K/8K fallbacks), then benchmark
your actual tasks. See [context sizing](CONTEXT_SIZING.md) for assumptions and
limits. `--context N` is an explicit override, not a fit guarantee.

There is no automatic "best model" ranking. A download/load test is not a quality
evaluation. Small models can confidently invent facts, code APIs and citations.
Comparing their answers is useful but agreement is not proof.

## Run an existing compatible GGUF

```bash
python3 run_server.py --model /path/to/your-model.gguf --thinking off
```

Use your own path. This single-model mode does not add the file to browser
selection, download it or verify its checksum. Verify the publisher's hash
separately. Raw safetensors/PyTorch/ONNX checkpoints are not direct replacements.
Vision/audio projectors and non-language image-generation models are not
configured by this launcher.

## Add a browser-selectable model

Edit `models.json` under `models`, adding a unique key and these fields:

```json
"your-model": {
  "name": "A readable model name and quantization",
  "notes": "Intended use and realistic hardware caveats",
  "license": "Check the original model license",
  "original_model": "https://huggingface.co/ORIGINAL/REPOSITORY",
  "repository": "PUBLISHER/GGUF-REPOSITORY",
  "revision": "REPLACE_WITH_THE_FULL_REPOSITORY_COMMIT",
  "filename": "your-model-Q4_K_M.gguf",
  "size_bytes": 123456789,
  "sha256": "REPLACE_WITH_THE_64_CHARACTER_FILE_SHA256",
  "context": 65536
}
```

The example values are placeholders, not a downloadable preset. Copy the exact
file size, full immutable repository revision and file SHA-256 from the actual
publisher. Choose a plain filename and inspect the original model license as
well as the conversion source. A publisher's hash checks integrity, not trust
or scientific quality.

Then run:

```bash
python3 manage_models.py --install your-model
python3 manage_models.py --browser
```

Restart a running router after installing weights to regenerate its list.
Only complete catalog files are listed; `.part` transfers are excluded. Each
switch unloads/reloads weights, with only one model instance allowed at once.

The package does not promise arbitrary/new model architectures will work with
its pinned runtime. Updating llama.cpp can require new compatible CPU and GPU
builds and fresh tests. Do not overwrite a working runtime blindly.

The historical `QWEN_MODEL_FILE`/`QWEN_MODEL_URL` environment overrides remain
available for advanced single-model downloads. Supply `QWEN_MODEL_SIZE` and
`QWEN_MODEL_SHA256` to retain strong integrity checks. Clear these overrides
before using the catalog menu or router.
