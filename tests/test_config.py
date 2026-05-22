from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interview_prep.infra.config import (
    DEFAULT_CONFIG_TEXT,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT,
    load_config,
    write_default_config,
)
from interview_prep.infra.llm import OllamaClient


class ConfigTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_file_is_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config("missing.toml")

        self.assertEqual(config.ollama.model, DEFAULT_OLLAMA_MODEL)
        self.assertEqual(config.ollama.base_url, DEFAULT_OLLAMA_BASE_URL)
        self.assertEqual(config.ollama.timeout_seconds, DEFAULT_OLLAMA_TIMEOUT)

    def test_default_ollama_runtime_is_gemma4(self) -> None:
        self.assertEqual(DEFAULT_OLLAMA_MODEL, "gemma4:e4b")
        self.assertEqual(OllamaClient().model, DEFAULT_OLLAMA_MODEL)
        self.assertIn('model = "gemma4:e4b"', DEFAULT_CONFIG_TEXT)

    def test_load_config_reads_toml_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.toml"
            path.write_text(
                """
                [ollama]
                model = "custom-model"
                base_url = "http://127.0.0.1:11434"
                timeout_seconds = 240
                """,
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(path)

        self.assertEqual(config.ollama.model, "custom-model")
        self.assertEqual(config.ollama.base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.ollama.timeout_seconds, 240.0)

    def test_env_overrides_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.toml"
            path.write_text(
                """
                [ollama]
                model = "file-model"
                base_url = "http://file:11434"
                timeout_seconds = 120
                """,
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "INTERVIEW_PREP_OLLAMA_MODEL": "env-model",
                    "INTERVIEW_PREP_OLLAMA_BASE_URL": "http://env:11434",
                    "INTERVIEW_PREP_OLLAMA_TIMEOUT": "300",
                },
            ):
                config = load_config(path)

        self.assertEqual(config.ollama.model, "env-model")
        self.assertEqual(config.ollama.base_url, "http://env:11434")
        self.assertEqual(config.ollama.timeout_seconds, 300.0)

    def test_write_default_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config" / "interview_prep.toml"
            written = write_default_config(path)

            self.assertEqual(written, path)
            self.assertIn("[ollama]", path.read_text(encoding="utf-8"))

    def test_config_show_cli_uses_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.toml"
            path.write_text(
                """
                [ollama]
                model = "cli-model"
                base_url = "http://cli:11434"
                timeout_seconds = 210
                """,
                encoding="utf-8",
            )
            process = subprocess.run(
                [sys.executable, "-m", "interview_prep", "config-show", "--config", str(path)],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("model = cli-model", process.stdout)
        self.assertIn("timeout_seconds = 210", process.stdout)


if __name__ == "__main__":
    unittest.main()
