from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("config/interview_prep.toml")
DEFAULT_OLLAMA_MODEL = "gemma4:e4b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_TIMEOUT = 180.0


@dataclass(frozen=True)
class OllamaSettings:
    model: str = DEFAULT_OLLAMA_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT


@dataclass(frozen=True)
class AppConfig:
    ollama: OllamaSettings = OllamaSettings()


DEFAULT_CONFIG_TEXT = f"""# Local interview-prep settings.
# Environment variables override this file:
# INTERVIEW_PREP_OLLAMA_MODEL
# INTERVIEW_PREP_OLLAMA_BASE_URL
# INTERVIEW_PREP_OLLAMA_TIMEOUT

[ollama]
model = "{DEFAULT_OLLAMA_MODEL}"
base_url = "{DEFAULT_OLLAMA_BASE_URL}"
timeout_seconds = {int(DEFAULT_OLLAMA_TIMEOUT)}
"""


def load_config(config_path: str | Path | None = DEFAULT_CONFIG_PATH) -> AppConfig:
    raw = _read_config(config_path)
    ollama = raw.get("ollama", {}) if isinstance(raw.get("ollama", {}), dict) else {}
    return AppConfig(
        ollama=OllamaSettings(
            model=os.getenv("INTERVIEW_PREP_OLLAMA_MODEL", str(ollama.get("model", DEFAULT_OLLAMA_MODEL))),
            base_url=os.getenv(
                "INTERVIEW_PREP_OLLAMA_BASE_URL",
                str(ollama.get("base_url", DEFAULT_OLLAMA_BASE_URL)),
            ),
            timeout_seconds=_env_float(
                "INTERVIEW_PREP_OLLAMA_TIMEOUT",
                ollama.get("timeout_seconds", DEFAULT_OLLAMA_TIMEOUT),
            ),
        )
    )


def write_default_config(config_path: str | Path = DEFAULT_CONFIG_PATH, overwrite: bool = False) -> Path:
    path = Path(config_path)
    if path.exists() and not overwrite:
        return path
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return path


def _read_config(config_path: str | Path | None) -> dict:
    if config_path is None:
        return {}
    path = Path(config_path)
    if not path.exists():
        return {}
    with path.open("rb") as file:
        data = tomllib.load(file)
    return data if isinstance(data, dict) else {}


def _env_float(name: str, default: object) -> float:
    raw = os.getenv(name)
    if raw is None:
        raw = default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return DEFAULT_OLLAMA_TIMEOUT
