"""Conservative, read-only context planning from GGUF metadata and free memory.

Standard library only. Estimates are not allocation guarantees or benchmarks.
The supported formulas assume one sequence, FP16 KV cache, no speculative MTP.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
import struct
import subprocess

GIB = 1024**3
MIB = 1024**2
PREFERRED_CONTEXT = 32768
CANDIDATES = (32768, 16384, 8192)


def gguf_metadata(path: Path) -> dict:
    """Read bounded GGUF v2/v3 model metadata, skipping tokenizer/tensor data."""
    size = path.stat().st_size
    limit = min(size, 64 * MIB)
    result = {}
    formats = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'f',
               7: '?', 10: 'Q', 11: 'q', 12: 'd'}
    with path.open('rb') as stream:
        def read(count):
            if count < 0 or stream.tell() + count > limit:
                raise ValueError('Truncated or oversized GGUF metadata.')
            data = stream.read(count)
            if len(data) != count:
                raise ValueError('Truncated GGUF metadata.')
            return data

        def number(fmt):
            return struct.unpack('<' + fmt, read(struct.calcsize(fmt)))[0]

        def skip(count):
            if count < 0 or stream.tell() + count > limit:
                raise ValueError('Truncated or oversized GGUF metadata.')
            stream.seek(count, 1)

        def string(keep):
            length = number('Q')
            if keep:
                if length > 65536:
                    raise ValueError('Oversized GGUF metadata string.')
                return read(length).decode('utf-8')
            skip(length)

        def value(kind, keep, depth=0):
            if kind in formats:
                if keep:
                    return number(formats[kind])
                skip(struct.calcsize(formats[kind]))
            elif kind == 8:
                return string(keep)
            elif kind == 9:
                if depth > 1:
                    raise ValueError('Unsupported nested GGUF metadata array.')
                item_type, count = number('I'), number('Q')
                if count > 10_000_000 or (keep and count > 4096):
                    raise ValueError('Oversized GGUF metadata array.')
                if not keep and item_type in formats:
                    skip(struct.calcsize(formats[item_type]) * count)
                    return None
                if keep:
                    return [value(item_type, True, depth + 1) for _ in range(count)]
                for _ in range(count):
                    value(item_type, False, depth + 1)
            else:
                raise ValueError(f'Unsupported GGUF metadata type: {kind}')

        if read(4) != b'GGUF' or number('I') not in (2, 3):
            raise ValueError('Context estimation requires a little-endian GGUF v2/v3 file.')
        number('Q')  # tensor count; tensors themselves are never read
        count = number('Q')
        if count > 100000:
            raise ValueError('Oversized GGUF metadata table.')
        for _ in range(count):
            key = string(True)
            keep = key == 'general.architecture' or not key.startswith(('tokenizer.', 'general.'))
            item = value(number('I'), keep)
            if keep:
                result[key] = item
    return result


def memory_estimate(metadata: dict, weights: int, context: int) -> dict:
    """FP16 K/V sum over cache-owning attention layers plus explicit margins.

    KV = sum(tokens_per_layer * KV_heads * (key_dim + value_dim) * 2 bytes).
    Gemma4 sharing is honored; its SWA is conservatively charged full context.
    Qwen35 recurrent layers have no growing attention KV; recurrent/compute
    state is covered by a separate heuristic allowance, not the KV formula.
    """
    arch = metadata.get('general.architecture')
    if arch not in {'qwen35', 'qwen35moe', 'qwen3', 'qwen3moe', 'qwen2', 'phi3', 'llama', 'gemma4'}:
        raise ValueError(f'No verified cache formula for architecture {arch!r}; use --context explicitly.')

    def field(name, default=None):
        return metadata.get(f'{arch}.{name}', default)

    def positive(value):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= 10_000_000:
            raise ValueError('Missing or invalid GGUF attention dimensions.')
        return value

    layers = positive(field('block_count'))
    if layers > 1024:
        raise ValueError('Unsupported GGUF layer count.')
    # MTP-only blocks are not active in this launcher.
    layers -= int(field('nextn_predict_layers', 0))
    positive(layers)

    def per_layer(name, index, default=None):
        item = field(name, default)
        if isinstance(item, list):
            if len(item) < layers:
                raise ValueError('Incomplete per-layer GGUF attention metadata.')
            item = item[index]
        return positive(item)

    recurrent = field('attention.recurrent_layers')
    if recurrent is not None and (not isinstance(recurrent, list) or len(recurrent) < layers
                                  or any(item not in (True, False, 0, 1) for item in recurrent)):
        raise ValueError('Invalid GGUF recurrent-layer metadata.')
    interval = positive(field('full_attention_interval', 4)) if arch.startswith('qwen35') else None
    shared = field('attention.shared_kv_layers', 0) if arch == 'gemma4' else 0
    if not isinstance(shared, int) or not 0 <= shared < layers:
        raise ValueError('Invalid GGUF shared-cache layer count.')
    embedding = field('embedding_length')
    kv, attention_layers = 0, 0
    for i in range(layers - shared):
        if interval and (bool(recurrent[i]) if recurrent is not None else (i + 1) % interval != 0):
            continue
        heads = per_layer('attention.head_count_kv', i, field('attention.head_count'))
        key = field('attention.key_length')
        if key is None:
            query_heads = per_layer('attention.head_count', i)
            if positive(embedding) % query_heads:
                raise ValueError('Cannot infer the attention head dimension exactly.')
            key = embedding // query_heads
        key = positive(key)
        val = positive(field('attention.value_length', key))
        if arch == 'gemma4':
            # Upper bound: use the larger SWA/global dimensions and full
            # context for every unique cache, not a fragile SWA approximation.
            key = max(key, positive(field('attention.key_length_swa', key)))
            val = max(val, positive(field('attention.value_length_swa', val)))
        kv += context * heads * (key + val) * 2
        attention_layers += 1
    # These allowances are deliberately labeled heuristics, not exact tensor
    # allocation measurements. File size is a conservative weight proxy.
    overhead = max(768 * MIB, weights // 10)
    if interval:
        overhead += 256 * MIB
    needed = weights + kv + overhead + (weights + kv) // 10
    return {'context': context, 'weights_bytes': weights, 'kv_bytes': kv,
            'overhead_bytes': overhead, 'estimated_bytes': needed,
            'attention_layers': attention_layers, 'architecture': arch,
            'notes': (['Gemma SWA cache charged at full context as a conservative upper bound.']
                      if arch == 'gemma4' else [])}


def available_ram() -> int | None:
    if os.name == 'nt':
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_uint32), ('load', ctypes.c_uint32)] + [
                (name, ctypes.c_uint64) for name in
                ('total_physical', 'available_physical', 'total_page', 'available_page',
                 'total_virtual', 'available_virtual', 'extended')]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.available_physical
        return None
    try:
        data = Path('/proc/meminfo').read_text()
        match = re.search(r'^MemAvailable:\s+(\d+)\s+kB', data, re.MULTILINE)
        if match:
            available = int(match[1]) * 1024
            # Honor the usual unified-container memory limit when available.
            limit, current = Path('/sys/fs/cgroup/memory.max'), Path('/sys/fs/cgroup/memory.current')
            if limit.is_file() and current.is_file() and limit.read_text().strip() != 'max':
                available = min(available, max(0, int(limit.read_text()) - int(current.read_text())))
            return available
    except (OSError, ValueError):
        pass
    try:
        return os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
    except (AttributeError, OSError, ValueError):
        return None


def gpu_memory(server: str, environment: dict, device: str | None) -> dict | None:
    """Use the selected runtime's device report; never install GPU utilities."""
    if not device or ',' in device:
        return None  # Multi-device/unified allocation is not inferred.
    try:
        result = subprocess.run([server, '--list-devices'], env=environment, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'^\s*' + re.escape(device) +
                      r': .*?\((\d+) MiB, (\d+) MiB free\)', result.stdout, re.MULTILINE)
    if not match:
        return None
    return {'device': device, 'total_bytes': int(match[1]) * MIB, 'free_bytes': int(match[2]) * MIB}


def choose_context(metadata: dict, weights: int, ram: int | None, gpu: dict | None = None,
                   gpu_expected: bool = False) -> dict:
    if ram is None:
        raise ValueError('Available RAM could not be measured; use --context N as an explicit override.')
    maximum = metadata.get(f"{metadata.get('general.architecture')}.context_length")
    if not isinstance(maximum, int) or maximum <= 0:
        raise ValueError('Missing trained context limit; use --context N explicitly.')
    reserve = max(2 * GIB, ram // 10)
    candidates = [memory_estimate(metadata, weights, size) for size in CANDIDATES if size <= maximum]
    fits_ram = [item for item in candidates if item['estimated_bytes'] <= ram - reserve]
    if not fits_ram:
        raise ValueError('Even 8K is not estimated to fit available RAM/model limits. Close workloads, '
                         'choose smaller weights, or use --context N explicitly. No model was started.')
    if gpu is not None:
        budget = max(0, gpu['free_bytes'] - max(512 * MIB, gpu['total_bytes'] // 10))
        fits_gpu = [item for item in fits_ram if item['estimated_bytes'] <= budget]
        if fits_gpu:
            chosen = fits_gpu[0]
            mode = 'estimated full GPU fit'
        elif weights + fits_ram[-1]['overhead_bytes'] > budget:
            # Large models cannot fit wholly in VRAM even without a KV cache.
            # RAM fit is checked, but llama.cpp must handle partial offload.
            chosen, mode = fits_ram[0], 'RAM fit only; partial GPU offload expected'
        else:
            chosen, mode = fits_ram[-1], 'RAM fit only; GPU fit not established even at 8K'
    elif gpu_expected:
        chosen = next((item for item in fits_ram if item['context'] <= 16384), fits_ram[-1])
        mode = 'RAM fit only; GPU memory unknown, conservative fallback'
    else:
        chosen, mode = fits_ram[0], 'estimated CPU/RAM fit'
    return dict(chosen, mode=mode, preferred_context=PREFERRED_CONTEXT,
                ram_available_bytes=ram, gpu=gpu,
                warning='Estimate only: allocations, other processes and runtime settings can change fit.')


def plan_models(models: dict[str, Path], ram: int | None, gpu: dict | None = None,
                gpu_expected: bool = False) -> dict:
    plans = {}
    for key, path in models.items():
        try:
            plans[key] = choose_context(gguf_metadata(path), path.stat().st_size, ram, gpu, gpu_expected)
        except (OSError, ValueError, UnicodeError, struct.error) as error:
            plans[key] = {'error': str(error), 'context': None}
    return plans


def describe(plans: dict) -> None:
    print('Context preflight (estimate, not an allocation guarantee):', flush=True)
    for key, plan in plans.items():
        if plan.get('error'):
            print(f"  {key}: unavailable in automatic mode: {plan['error']}", flush=True)
            continue
        print(f"  {key}: {plan['context']:,} tokens; KV {plan['kv_bytes'] / GIB:.2f} GiB; "
              f"weights+cache+margins {plan['estimated_bytes'] / GIB:.2f} GiB; {plan['mode']}", flush=True)
        if plan['context'] != PREFERRED_CONTEXT:
            print(f"    Preferred 32K was reduced to {plan['context']:,}; match the IDE context to this value.",
                  flush=True)
        for note in plan['notes']:
            print(f'    {note}', flush=True)
