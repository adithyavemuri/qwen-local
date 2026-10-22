"""Offline configuration/launcher tests: no weights, network or compiler needed."""
import argparse
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import model_config
import run_server
import setup_gpu


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_default_has_immutable_revision_and_digest(self):
        model = model_config.selection()
        self.assertEqual(model["preset"], "qwen3.5-4b")
        self.assertIn(model["revision"], model["url"])
        self.assertEqual(len(model["revision"]), 40)
        self.assertEqual(len(model["sha256"]), 64)
        self.assertEqual(model["size_bytes"], 2740937888)

    def test_all_presets_share_the_runtime_and_have_integrity_pins(self):
        for key in model_config.catalog()["models"]:
            with self.subTest(preset=key):
                spec = model_config.selection(key)
                self.assertEqual(spec["llama_commit"], model_config.selection()["llama_commit"])
                self.assertEqual(len(spec["revision"]), 40)
                self.assertEqual(len(spec["sha256"]), 64)
                self.assertGreater(spec["size_bytes"], 0)

    def test_explicit_preset_overrides_environment(self):
        os.environ["QWEN_MODEL_PRESET"] = "qwen3-30b-a3b"
        self.assertEqual(model_config.selection()["preset"], "qwen3-30b-a3b")
        self.assertEqual(model_config.selection("qwen3.8-27b")["preset"], "qwen3.8-27b")

    def test_unknown_preset_is_not_silently_replaced(self):
        with self.assertRaises(ValueError):
            model_config.selection("not-a-model")

    def test_custom_filename_needs_download_url(self):
        os.environ["QWEN_MODEL_FILE"] = "custom.gguf"
        with self.assertRaises(ValueError):
            model_config.selection()

    def test_custom_url_clears_builtin_digest_and_size(self):
        os.environ.update(QWEN_MODEL_FILE="custom.gguf", QWEN_MODEL_URL="https://example.org/custom.gguf")
        model = model_config.selection()
        self.assertEqual(model["sha256"], "")
        self.assertEqual(model["size_bytes"], 0)

    def test_rejects_traversal_non_https_and_bad_checksum(self):
        for values in (
            {"QWEN_MODEL_FILE": "../outside.gguf", "QWEN_MODEL_URL": "https://example.org/model"},
            {"QWEN_MODEL_URL": "http://example.org/model"},
            {"QWEN_MODEL_URL": "https://example.org/model", "QWEN_MODEL_SHA256": "not-a-hash"},
        ):
            with self.subTest(values=values), patch.dict(os.environ, values, clear=True):
                with self.assertRaises(ValueError):
                    model_config.selection()

    def test_runtime_pin_and_custom_override(self):
        self.assertEqual(model_config.selection()["llama_ref"], "v0.7.0")
        self.assertEqual(len(model_config.selection()["llama_commit"]), 40)
        os.environ["LLAMA_CPP_REF"] = "custom-tag"
        self.assertEqual(model_config.selection()["llama_commit"], "")

    def test_integrity_checks_size_header_and_full_checksum(self):
        content = b"GGUF" + b"test-fixture" * 20
        spec = {"size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.gguf.part"
            path.write_bytes(content)
            with contextlib.redirect_stdout(io.StringIO()):
                model_config.verify_model(path, spec)
            for bad in (content[:-1], b"FAIL" + content[4:], content[:-1] + b"x"):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    model_config.verify_model(path, spec)
            self.assertTrue(path.exists(), "Verification must not delete or accept a damaged file")

    def test_runtime_manifest_must_match_pinned_commit(self):
        spec = model_config.selection()
        with tempfile.TemporaryDirectory() as directory, patch.object(model_config, "ROOT", Path(directory)):
            runtime = Path(directory) / "runtime"
            runtime.mkdir()
            binary = runtime / ("llama-server.exe" if os.name == "nt" else "llama-server")
            binary.touch()
            manifest = runtime / "build-manifest.json"
            self.assertFalse(model_config.runtime_ready(spec))
            manifest.write_text(json.dumps({"ref": spec["llama_ref"], "commit": "wrong"}))
            self.assertFalse(model_config.runtime_ready(spec))
            manifest.write_text(json.dumps({"ref": spec["llama_ref"], "commit": spec["llama_commit"]}))
            self.assertTrue(model_config.runtime_ready(spec))

    def test_launcher_resolves_selected_filename_and_thinking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runtime").mkdir()
            server = root / "runtime" / ("llama-server.exe" if os.name == "nt" else "llama-server")
            server.touch()
            (root / "models").mkdir()
            spec = model_config.selection("qwen3-30b-a3b")
            model = root / "models" / spec["filename"]
            model.touch()
            args = argparse.Namespace(preset="qwen3-30b-a3b", model=None, server=None,
                                      host="127.0.0.1", port=8080, context=None, threads=8,
                                      gpu_layers=0, thinking="off", backend="cpu")
            with patch.object(run_server, "__file__", str(root / "run_server.py")):
                result = run_server.command(args)
            self.assertEqual(result[result.index("--model") + 1], str(model))
            self.assertEqual(result[result.index("--ctx-size") + 1], "65536")
            self.assertEqual(result[result.index("--parallel") + 1], "1")
            self.assertEqual(result[result.index("--reasoning") + 1], "off")
            self.assertEqual(result[result.index("--cors-origins") + 1], "localhost")
            self.assertIn("--no-agent", result)

    def test_list_models_needs_neither_runtime_nor_model(self):
        result = subprocess.run([sys.executable, str(ROOT / "run_server.py"), "--list-models"],
                                capture_output=True, text=True, check=True)
        self.assertIn("qwen3.5-4b (default)", result.stdout)
        self.assertIn("qwen3.8-27b", result.stdout)
        self.assertIn("gemma4-e2b", result.stdout)
        self.assertIn("phi4-mini", result.stdout)
        self.assertIn("qwen3-30b-a3b", result.stdout)
        self.assertIn("installed", result.stdout)

    def test_gpu_selection_auto_layers_and_cpu_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / "llama-server"
            model = root / "example.gguf"
            server.touch()
            model.touch()
            args = argparse.Namespace(preset=None, model=model, server=None, backend="auto",
                                      host="127.0.0.1", port=8080, context=4096, threads=8,
                                      gpu_layers=None, thinking="off")
            with patch.object(run_server, "gpu_runtime", return_value={"executable": server, "device": "Vulkan1"}):
                result = run_server.command(args)
            self.assertEqual(result[0], str(server))
            self.assertEqual(result[result.index("--n-gpu-layers") + 1], "auto")
            self.assertEqual(result[result.index("--device") + 1], "Vulkan1")
            args.device = "Vulkan0"
            with patch.object(run_server, "gpu_runtime", return_value={"executable": server, "device": "Vulkan1"}):
                result = run_server.command(args)
            self.assertEqual(result[result.index("--device") + 1], "Vulkan0")
            args.device = None
            args.backend = "cpu"
            args.server = server
            result = run_server.command(args)
            self.assertEqual(result[result.index("--n-gpu-layers") + 1], "0")

    def test_explicit_gpu_fails_if_not_installed(self):
        args = argparse.Namespace(preset=None, server=None, backend="vulkan")
        with patch.object(run_server, "gpu_runtime", return_value=None):
            with self.assertRaisesRegex(ValueError, "setup_gpu.py"):
                run_server.command(args)

    def test_gpu_library_environment_is_scoped_to_selected_executable(self):
        gpu = {"executable": Path("/tmp/gpu-server").resolve(), "libraries": [Path("/tmp/libs")]}
        with patch.object(run_server, "gpu_runtime", return_value=gpu):
            self.assertEqual(run_server.server_environment("/tmp/gpu-server")["LD_LIBRARY_PATH"], "/tmp/libs")
            self.assertNotIn("LD_LIBRARY_PATH", run_server.server_environment("/tmp/cpu-server"))
        self.assertNotIn("LD_LIBRARY_PATH", os.environ)

    def test_gpu_manifest_rejects_wrong_pin_and_escaping_paths(self):
        spec = model_config.selection()
        with tempfile.TemporaryDirectory() as directory, patch.object(model_config, "ROOT", Path(directory)):
            root = Path(directory) / "runtime/vulkan"
            root.mkdir(parents=True)
            (root / "llama-server").touch()
            manifest = {"ref": spec["llama_ref"], "commit": spec["llama_commit"], "backend": "vulkan",
                        "server": "llama-server", "library_paths": ["."]}
            path = root / "build-manifest.json"
            path.write_text(json.dumps(manifest))
            self.assertIsNotNone(model_config.gpu_runtime(spec))
            for changes in ({"commit": "wrong"}, {"server": "../../outside"},
                            {"library_paths": ["../../../"]}):
                path.write_text(json.dumps(dict(manifest, **changes)))
                self.assertIsNone(model_config.gpu_runtime(spec))

    def test_archive_extraction_rejects_traversal_and_external_links(self):
        import tarfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, link in (("../outside", ""), ("link", "../../outside")):
                archive = root / "test.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    member = tarfile.TarInfo(name)
                    if link:
                        member.type = tarfile.SYMTYPE
                        member.linkname = link
                    bundle.addfile(member)
                with self.assertRaises(ValueError):
                    setup_gpu.extract(archive, root / "extracted")

    def test_smoke_http_helper_accepts_gzip_browser_assets(self):
        spec = importlib.util.spec_from_file_location("qwen_smoke", ROOT / "examples/smoke_test.py")
        smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smoke)
        response = io.BytesIO(gzip.compress(b"<html><script>test</script></html>"))
        response.headers = {"Content-Encoding": "gzip"}
        with patch.object(smoke.urllib.request, "urlopen", return_value=response) as opened:
            result = smoke.request("http://127.0.0.1:8080/")
        self.assertIn(b"<html", result)
        self.assertEqual(opened.call_args.args[0].get_header("Accept-encoding"), "gzip")

    def test_dry_run_never_attempts_bootstrap(self):
        with patch.object(run_server, "command", return_value=["fake-server"]), \
             patch.object(run_server, "runtime_ready", side_effect=AssertionError("bootstrap attempted")), \
             patch.object(sys, "argv", ["run_server.py", "--setup-if-needed", "--dry-run"]), \
             contextlib.redirect_stdout(io.StringIO()):
            run_server.main()

    def test_installed_gpu_does_not_trigger_unnecessary_cpu_build(self):
        with patch.object(run_server, "command", return_value=["fake-server"]), \
             patch.object(run_server, "automatic_contexts", return_value={"qwen3.5-4b": {"context": 65536}}), \
             patch.object(run_server, "gpu_runtime", return_value={"executable": Path("fake-server")}), \
             patch.object(run_server, "runtime_ready", return_value=False), \
             patch.object(run_server, "model_ready", return_value=True), \
             patch.object(run_server, "server_environment", return_value={}), \
             patch.object(run_server.subprocess, "run", side_effect=AssertionError("unexpected setup")), \
             patch.object(run_server.subprocess, "call", return_value=0), \
             patch.object(sys, "argv", ["run_server.py", "--setup-if-needed"]), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                run_server.main()
        self.assertEqual(result.exception.code, 0)

    @unittest.skipIf(os.name == "nt", "Bash syntax check is performed on Linux")
    def test_bash_syntax_and_unknown_preset(self):
        subprocess.run(["bash", "-n", str(ROOT / "setup_qwen.sh"), str(ROOT / "start_qwen.sh")], check=True)
        result = subprocess.run(["bash", str(ROOT / "setup_qwen.sh"), "--model", "bad", "--preflight"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown preset", result.stderr)


if __name__ == "__main__":
    unittest.main()
