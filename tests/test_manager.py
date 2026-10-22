"""Menu, consent and portable command construction; never download or build."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import manage_models
import model_config


class ManagerTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        root = patch.object(manage_models, "ROOT", self.root)
        root.start()
        self.addCleanup(root.stop)
        self.spec = dict(model_config.selection("phi4-mini"), size_bytes=4)
        selected = patch.object(manage_models, "selection", return_value=self.spec)
        selected.start()
        self.addCleanup(selected.stop)

    def test_platform_commands_are_argument_lists_and_download_weights_only(self):
        linux = manage_models.setup_command("phi4-mini", windows=False)
        windows = manage_models.setup_command("phi4-mini", windows=True)
        self.assertEqual(linux[0], "bash")
        self.assertIn("--model-only", linux)
        self.assertEqual(windows[:3], ["powershell.exe", "-NoProfile", "-File"])
        self.assertIn("-ModelOnly", windows)
        self.assertEqual(windows[windows.index("-ModelPreset") + 1], "phi4-mini")

    def test_declining_download_never_runs_setup(self):
        with patch("builtins.input", return_value="n"), patch.object(manage_models.subprocess, "call") as called:
            self.assertEqual(manage_models.install("phi4-mini"), 1)
        called.assert_not_called()
        self.assertFalse((self.root / "models").exists())

    def test_dry_run_needs_neither_input_nor_runtime(self):
        with patch("builtins.input", side_effect=AssertionError("unexpected question")), \
             patch.object(manage_models.subprocess, "call", side_effect=AssertionError("unexpected command")):
            self.assertEqual(manage_models.install("phi4-mini", dry_run=True), 0)
            self.assertEqual(manage_models.start("phi4-mini", dry_run=True), 0)
            self.assertEqual(manage_models.browser(dry_run=True), 0)

    def test_confirmed_download_preserves_setup_exit_code(self):
        with patch.object(manage_models.subprocess, "call", return_value=7) as called:
            self.assertEqual(manage_models.install("phi4-mini", yes=True), 7)
        self.assertIn("phi4-mini", called.call_args.args[0])

    def test_browser_requires_an_installed_model(self):
        with patch.object(manage_models.subprocess, "call") as called:
            with self.assertRaisesRegex(ValueError, "Install at least one"):
                manage_models.browser()
        called.assert_not_called()

    def test_failed_install_does_not_launch_server(self):
        with patch.object(manage_models, "install", return_value=1), \
             patch.object(manage_models, "run") as called:
            self.assertEqual(manage_models.start("phi4-mini"), 1)
        called.assert_not_called()

    def test_menu_can_exit_without_side_effects(self):
        with patch("builtins.input", return_value="q"), patch.object(manage_models, "show_models"), \
             patch.object(manage_models.subprocess, "call") as called:
            self.assertEqual(manage_models.menu(), 0)
        called.assert_not_called()

    def test_tool_verification_rejects_modified_and_truncated_archives(self):
        path = self.root / "tool.tar.gz"
        content = b"tool archive fixture"
        spec = {"size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        path.write_bytes(content)
        model_config.verify_file(path, spec)
        for bad in (content[:-1], b"X" + content[1:]):
            path.write_bytes(bad)
            with self.assertRaises(ValueError):
                model_config.verify_file(path, spec)
        self.assertTrue(path.exists())

    def test_catalog_tool_inspection_and_invalid_field(self):
        root = Path(model_config.__file__).resolve().parent
        result = subprocess.run([sys.executable, str(root / "model_config.py"), "--tool", "cmake",
                                 "--field", "sha256"], capture_output=True, text=True, check=True)
        self.assertEqual(len(result.stdout.strip()), 64)
        result = subprocess.run([sys.executable, str(root / "model_config.py"), "--tool", "cmake",
                                 "--field", "missing"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
