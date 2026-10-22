"""Offline tests for installed-only browser model routing."""
import argparse
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import model_router
import run_server


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "models").mkdir()
        self.specs = {key: {"filename": key + ".gguf", "size_bytes": 4, "context": 4096}
                      for key in ("small", "large", "missing")}
        (self.root / "models/small.gguf").write_bytes(b"GGUF")
        (self.root / "models/large.gguf").write_bytes(b"GGUF")
        for target, value in (("catalog", lambda: {"default": "small", "models": self.specs}),
                              ("selection", lambda key: self.specs[key])):
            mocked = patch.object(model_router, target, value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_only_complete_installed_models_are_listed(self):
        (self.root / "models/missing.gguf.part").write_bytes(b"GGUF")
        content = model_router.configuration(self.root)
        self.assertIn("[small]", content)
        self.assertIn("[large]", content)
        self.assertNotIn("[missing]", content)
        self.assertEqual(content.count("load-on-startup = true"), 1)
        self.assertNotIn("hf-repo", content)
        self.assertNotIn("https://", content)
        (self.root / "models/large.gguf").write_bytes(b"BAD")
        self.assertNotIn("[large]", model_router.configuration(self.root))

    def test_explicit_missing_startup_model_never_downloads(self):
        with self.assertRaisesRegex(ValueError, "not installed"):
            model_router.configuration(self.root, "missing")

    def test_context_override_applies_to_every_installed_model(self):
        content = model_router.configuration(self.root, context=32768)
        self.assertEqual(content.count("ctx-size = 32768"), 2)
        self.assertNotIn("ctx-size = 4096", content)
        # Omitting the override still preserves individual catalog defaults.
        self.specs["large"]["context"] = 8192
        defaults = model_router.configuration(self.root)
        self.assertIn("ctx-size = 4096", defaults)
        self.assertIn("ctx-size = 8192", defaults)

    def test_prepare_writes_the_context_override(self):
        path = model_router.prepare(self.root, 18080, "large", context=32768)
        self.assertEqual(path.read_text(), model_router.configuration(self.root, "large", 32768))
        self.assertEqual(path.read_text().count("ctx-size = 32768"), 2)

    def test_invalid_context_is_rejected_before_writing(self):
        for value in (0, -1, True, "32768"):
            with self.subTest(context=value), self.assertRaisesRegex(ValueError, "positive integer"):
                model_router.prepare(self.root, 18080, context=value)
        self.assertFalse((self.root / "runtime").exists())

    def test_per_model_plans_override_parent_and_omit_unavailable_models(self):
        contexts = {'small': 32768, 'large': 16384}
        path = model_router.prepare(self.root, 18080, 'small', context=32768, contexts=contexts)
        content = path.read_text()
        self.assertIn('ctx-size = 32768', content)
        self.assertIn('ctx-size = 16384', content)
        self.assertNotIn('[missing]', content)
        self.assertNotIn('[large]', model_router.configuration(self.root, contexts={'small': 16384}))
        with self.assertRaisesRegex(ValueError, 'positive integers'):
            model_router.configuration(self.root, contexts={'small': 0})

    def test_explicit_startup_and_fallback_if_default_is_missing(self):
        content = model_router.configuration(self.root, "large")
        self.assertIn("[large]\nmodel =", content)
        self.assertEqual(content.count("load-on-startup = true"), 1)
        (self.root / "models/small.gguf").unlink()
        self.assertIn("load-on-startup = true", model_router.configuration(self.root))
        (self.root / "models/large.gguf").unlink()
        with self.assertRaisesRegex(ValueError, "No complete"):
            model_router.configuration(self.root)

    def test_custom_download_overrides_are_not_applied_to_all_router_entries(self):
        os.environ["QWEN_MODEL_URL"] = "https://example.org/other.gguf"
        with self.assertRaisesRegex(ValueError, "clear custom"):
            model_router.configuration(self.root)

    def test_prepare_is_local_and_environment_does_not_change_global_cache(self):
        path = model_router.prepare(self.root, 18080)
        self.assertTrue(path.is_relative_to(self.root / "runtime"))
        self.assertEqual(path.read_text(), model_router.configuration(self.root))
        with patch.object(run_server, "__file__", str(self.root / "run_server.py")), \
             patch.object(run_server, "gpu_runtime", return_value=None):
            environment = run_server.server_environment("server", router=True)
        self.assertEqual(environment["LLAMA_CACHE"], str(self.root / "runtime/router-cache"))
        self.assertNotIn("LLAMA_CACHE", os.environ)

    def test_inherited_single_model_or_external_directory_does_not_replace_router(self):
        os.environ.update(LLAMA_ARG_MODEL="outside.gguf", LLAMA_ARG_HF_REPO="outside/model",
                          LLAMA_ARG_MODELS_DIR="/outside/models")
        with patch.object(run_server, "gpu_runtime", return_value=None):
            environment = run_server.server_environment("server", router=True)
            single = run_server.server_environment("server")
        for key in ("LLAMA_ARG_MODEL", "LLAMA_ARG_HF_REPO", "LLAMA_ARG_MODELS_DIR"):
            self.assertNotIn(key, environment)
            self.assertIn(key, single)
            self.assertIn(key, os.environ)

    def test_router_command_uses_offline_one_model_mode_without_single_model(self):
        server = self.root / "server"
        server.touch()
        args = argparse.Namespace(preset=None, model=None, server=server, backend="cpu", router=True,
                                  host="127.0.0.1", port=8080, context=32768, threads=8,
                                  gpu_layers=None, thinking="off")
        with patch.object(run_server, "__file__", str(self.root / "run_server.py")), \
             patch.object(model_router, "configuration", wraps=model_router.configuration) as configured:
            result = run_server.command(args)
        configured.assert_called_once_with(self.root, None, 32768)
        self.assertEqual(result[result.index("--ctx-size") + 1], "32768")
        self.assertIn("--models-preset", result)
        self.assertEqual(result[result.index("--models-max") + 1], "1")
        self.assertIn("--offline", result)
        self.assertIn("--no-agent", result)
        self.assertIn("--no-ui-mcp-proxy", result)
        self.assertNotIn("--model", result)
        self.assertFalse((self.root / "runtime").exists(), "Command/dry-run must not write files")
        args.model = self.root / "models/small.gguf"
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            run_server.command(args)


if __name__ == "__main__":
    unittest.main()
