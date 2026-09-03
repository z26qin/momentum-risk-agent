"""Small local environment loader for DeepSeek and LangSmith configuration."""

from __future__ import annotations

import os
from pathlib import Path

DEEPSEEK_ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
)

LANGSMITH_ENV_KEYS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
    "LANGCHAIN_ENDPOINT",
)

DEFAULT_LANGSMITH_PROJECT = "momentum-risk-agent"


def _load_allowlisted_env(path: Path, keys: tuple[str, ...]) -> tuple[str, ...]:
    if not path.is_file():
        return ()
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, raw_value = line.partition("=")
        key = key.strip()
        if not separator or key not in keys or key in os.environ:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)


def load_deepseek_env(path: Path) -> tuple[str, ...]:
    """Load known DeepSeek values without overriding the process environment."""
    return _load_allowlisted_env(path, DEEPSEEK_ENV_KEYS)


def load_langsmith_env(path: Path) -> tuple[str, ...]:
    """Load known LangSmith values without overriding the process environment."""
    loaded = _load_allowlisted_env(path, LANGSMITH_ENV_KEYS)
    tracing_on = _env_flag("LANGSMITH_TRACING") or _env_flag("LANGCHAIN_TRACING_V2")
    if tracing_on and not os.environ.get("LANGSMITH_PROJECT") and not os.environ.get(
        "LANGCHAIN_PROJECT"
    ):
        os.environ["LANGSMITH_PROJECT"] = DEFAULT_LANGSMITH_PROJECT
        loaded = (*loaded, "LANGSMITH_PROJECT")
    return loaded


def load_local_env(path: Path) -> tuple[str, ...]:
    return (*load_deepseek_env(path), *load_langsmith_env(path))


def _env_flag(key: str) -> bool:
    return os.environ.get(key, "").strip().lower() in {"1", "true", "yes"}
