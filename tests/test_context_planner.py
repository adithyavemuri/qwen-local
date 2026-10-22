"""Analytical and synthetic-GGUF tests: no GPU, network, weights or installs."""
import argparse
import contextlib
import io
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import context_planner as planner
import run_server


def metadata(arch='phi3'):
    if arch == 'qwen35':
        values = {'block_count': 32, 'embedding_length': 2560,
                  'attention.head_count': 16, 'attention.head_count_kv': 4,
                  'attention.key_length': 256, 'attention.value_length': 256,
                  'full_attention_interval': 4, 'context_length': 262144}
    else:
        values = {'block_count': 32, 'embedding_length': 3072,
                  'attention.head_count': 24, 'attention.head_count_kv': 8,
                  'context_length': 131072}
    return {'general.architecture': arch, **{f'{arch}.{key}': value for key, value in values.items()}}


def fixture(values):
    def string(value):
        data = value.encode()
        return struct.pack('<Q', len(data)) + data

    def encode(value):
        if isinstance(value, str):
            return 8, string(value)
        if isinstance(value, list):
            return 9, struct.pack('<IQ', 7, len(value)) + bytes(value)
        return 4, struct.pack('<I', value)

    rows = []
    for key, value in values.items():
        kind, data = encode(value)
        rows.append(string(key) + struct.pack('<I', kind) + data)
    return b'GGUF' + struct.pack('<IQQ', 3, 0, len(rows)) + b''.join(rows)


class ContextPlannerTests(unittest.TestCase):
    def test_qwen_hybrid_formula_is_one_gib_at_32k(self):
        estimate = planner.memory_estimate(metadata('qwen35'), 3 * planner.GIB, 32768)
        self.assertEqual(estimate['kv_bytes'], planner.GIB)
        self.assertEqual(estimate['attention_layers'], 8)
        self.assertGreater(estimate['estimated_bytes'], 4 * planner.GIB)

    def test_phi_formula_is_four_gib_at_32k(self):
        estimate = planner.memory_estimate(metadata(), 2 * planner.GIB, 32768)
        self.assertEqual(estimate['kv_bytes'], 4 * planner.GIB)
        self.assertEqual(estimate['attention_layers'], 32)

    def test_explicit_recurrent_pattern_and_shared_cache(self):
        data = metadata('qwen35')
        data['qwen35.attention.recurrent_layers'] = [True] * 31 + [False]
        self.assertEqual(planner.memory_estimate(data, 1, 32768)['kv_bytes'], planner.GIB // 8)
        gemma = {'general.architecture': 'gemma4', 'gemma4.block_count': 35,
                 'gemma4.attention.shared_kv_layers': 20,
                 'gemma4.attention.head_count_kv': 1, 'gemma4.attention.key_length': 512,
                 'gemma4.attention.value_length': 512, 'gemma4.attention.key_length_swa': 256,
                 'gemma4.attention.value_length_swa': 256}
        estimate = planner.memory_estimate(gemma, 1, 32768)
        self.assertEqual(estimate['attention_layers'], 15)
        self.assertEqual(estimate['kv_bytes'], 15 * 32768 * 1 * (512 + 512) * 2)
        self.assertTrue(estimate['notes'])

    def test_prefer_64k_with_sufficient_memory(self):
        gpu = {'free_bytes': 8 * planner.GIB, 'total_bytes': 8 * planner.GIB}
        plan = planner.choose_context(metadata('qwen35'), 2740937888, 50 * planner.GIB, gpu)
        self.assertEqual(plan['context'], 65536)
        self.assertEqual(plan['preferred_context'], 65536)
        self.assertEqual(plan['mode'], 'estimated full GPU fit')

    def test_fallback_from_64k_to_32k_when_gpu_budget_is_tighter(self):
        gpu = {'free_bytes': 6 * planner.GIB, 'total_bytes': 6 * planner.GIB}
        plan = planner.choose_context(metadata('qwen35'), 2740937888, 50 * planner.GIB, gpu)
        self.assertEqual(plan['context'], 32768)
        self.assertEqual(plan['preferred_context'], 65536)
        self.assertEqual(plan['mode'], 'estimated full GPU fit')

    def test_64k_cache_formula_doubles_32k_without_changing_weights(self):
        for arch in ('qwen35', 'phi3'):
            with self.subTest(architecture=arch):
                small = planner.memory_estimate(metadata(arch), 3 * planner.GIB, 32768)
                large = planner.memory_estimate(metadata(arch), 3 * planner.GIB, 65536)
                self.assertEqual(large['kv_bytes'], 2 * small['kv_bytes'])
                self.assertEqual(large['weights_bytes'], small['weights_bytes'])

    def test_gpu_fallbacks_are_16k_then_8k(self):
        # Phi KV is 4/2/1 GiB at 32/16/8K. Include all overhead and headroom.
        for free, expected in ((6.2, 16384), (5.0, 8192)):
            gpu = {'free_bytes': int(free * planner.GIB), 'total_bytes': 8 * planner.GIB}
            plan = planner.choose_context(metadata(), 2 * planner.GIB, 50 * planner.GIB, gpu)
            self.assertEqual(plan['context'], expected)
            self.assertEqual(plan['mode'], 'estimated full GPU fit')

    def test_cpu_uses_ram_budget_and_larger_model_is_explicitly_partial(self):
        plan = planner.choose_context(metadata(), 2 * planner.GIB, 50 * planner.GIB)
        self.assertEqual(plan['context'], 65536)
        self.assertEqual(plan['mode'], 'estimated CPU/RAM fit')
        gpu = {'free_bytes': 6 * planner.GIB, 'total_bytes': 6 * planner.GIB}
        plan = planner.choose_context(metadata('qwen35'), 18 * planner.GIB, 50 * planner.GIB, gpu)
        self.assertEqual(plan['context'], 65536)
        self.assertIn('partial GPU offload', plan['mode'])

    def test_unknown_gpu_does_not_claim_gpu_fit(self):
        plan = planner.choose_context(metadata(), 2 * planner.GIB, 50 * planner.GIB, gpu_expected=True)
        self.assertEqual(plan['context'], 16384)
        self.assertIn('GPU memory unknown', plan['mode'])

    def test_insufficient_ram_unknown_arch_and_model_limit_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, 'Even 8K'):
            planner.choose_context(metadata(), 2 * planner.GIB, 3 * planner.GIB)
        with self.assertRaisesRegex(ValueError, 'Available RAM'):
            planner.choose_context(metadata(), 1, None)
        data = metadata()
        data['general.architecture'] = 'unknown'
        data['unknown.context_length'] = 32768
        with self.assertRaisesRegex(ValueError, 'No verified cache formula'):
            planner.choose_context(data, 1, 50 * planner.GIB)
        data = metadata()
        data['phi3.context_length'] = 4096
        with self.assertRaisesRegex(ValueError, 'Even 8K'):
            planner.choose_context(data, 1, 50 * planner.GIB)

    def test_metadata_reader_roundtrip_and_invalid_inputs(self):
        data = metadata('qwen35')
        data['qwen35.attention.recurrent_layers'] = [True] * 32
        data['tokenizer.chat_template'] = 'private fixture deliberately skipped'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.gguf'
            raw = fixture(data)
            path.write_bytes(raw)
            read = planner.gguf_metadata(path)
            self.assertNotIn('tokenizer.chat_template', read)
            self.assertEqual(read['qwen35.attention.recurrent_layers'], [True] * 32)
            self.assertEqual(read['qwen35.attention.key_length'], 256)
            for invalid in (b'BAD!', raw[:20], raw[:-1], b'GGUF' + struct.pack('<IQQ', 3, 0, 999999)):
                path.write_bytes(invalid)
                with self.assertRaises((ValueError, UnicodeError)):
                    planner.gguf_metadata(path)

    def test_device_probe_uses_matching_device_and_handles_failures(self):
        report = ('Vulkan0: Intel (32000 MiB, 30000 MiB free)\n'
                  'Vulkan1: NVIDIA (6141 MiB, 5700 MiB free)\n')
        with patch.object(planner.subprocess, 'run', return_value=argparse.Namespace(stdout=report)):
            gpu = planner.gpu_memory('server', {}, 'Vulkan1')
            self.assertEqual(gpu['free_bytes'], 5700 * planner.MIB)
            self.assertIsNone(planner.gpu_memory('server', {}, 'Vulkan9'))
            self.assertIsNone(planner.gpu_memory('server', {}, 'Vulkan0,Vulkan1'))
        with patch.object(planner.subprocess, 'run', side_effect=OSError('not present')):
            self.assertIsNone(planner.gpu_memory('server', {}, 'Vulkan1'))

    def test_windows_ram_probe_reads_available_not_total_memory(self):
        def read_status(pointer):
            pointer._obj.total_physical = 64 * planner.GIB
            pointer._obj.available_physical = 20 * planner.GIB
            return 1
        library = SimpleNamespace(kernel32=SimpleNamespace(GlobalMemoryStatusEx=read_status))
        with patch.object(planner.os, 'name', 'nt'), \
             patch.object(planner.ctypes, 'windll', library, create=True):
            self.assertEqual(planner.available_ram(), 20 * planner.GIB)

    def test_trained_context_limit_is_respected(self):
        data = metadata()
        data['phi3.context_length'] = 16384
        plan = planner.choose_context(data, 1, 50 * planner.GIB)
        self.assertEqual(plan['context'], 16384)

    def test_unavailable_model_does_not_hide_other_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.gguf'
            path.write_bytes(fixture(metadata('qwen35')))
            plans = planner.plan_models({'small': path, 'missing': path.with_name('missing.gguf')},
                                        50 * planner.GIB)
            self.assertEqual(plans['small']['context'], 65536)
            self.assertIsNone(plans['missing']['context'])

    def test_main_passes_individual_contexts_to_router_and_explicit_override_skips_plan(self):
        plans = {'qwen3.5-4b': {'context': 65536}, 'phi4-mini': {'context': 8192}}
        for explicit in (False, True):
            args = ['run_server.py', '--router', '--thinking', 'off']
            if explicit:
                args += ['--context', '131072']
            with patch.dict(os.environ, {}, clear=True), \
                 patch.object(sys, 'argv', args), \
                 patch.object(run_server, 'command', return_value=['fake-server']), \
                 patch.object(run_server, 'automatic_contexts', return_value=plans) as planned, \
                 patch.object(run_server.model_router, 'prepare') as prepare, \
                 patch.object(run_server, 'server_environment', return_value={}), \
                 patch.object(run_server.subprocess, 'call', return_value=0), \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                run_server.main()
            if explicit:
                planned.assert_not_called()
                self.assertEqual(prepare.call_args.args[3:], (131072, None))
            else:
                planned.assert_called_once()
                self.assertEqual(prepare.call_args.args[3:], (65536, {'qwen3.5-4b': 65536, 'phi4-mini': 8192}))

    def test_context_report_does_not_setup_write_or_start(self):
        with patch.object(sys, 'argv', ['run_server.py', '--context-report', '--setup-if-needed']), \
             patch.object(run_server, 'command', return_value=['fake-server']), \
             patch.object(run_server, 'automatic_contexts', return_value={}), \
             patch.object(run_server.subprocess, 'run', side_effect=AssertionError('setup attempted')), \
             patch.object(run_server.subprocess, 'call', side_effect=AssertionError('server started')), \
             patch.object(run_server.model_router, 'prepare', side_effect=AssertionError('INI written')), \
             contextlib.redirect_stdout(io.StringIO()):
            run_server.main()


if __name__ == '__main__':
    unittest.main()
