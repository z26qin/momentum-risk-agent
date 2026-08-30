"""Small local environment loader for DeepSeek configuration."""

from __future__ import annotations

import os
from pathlib import Path

DEEPSEEK_ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
)


def load_deepseek_env(path: Path) -> tuple[str, ...]:
    """Load known DeepSeek values without overriding the process environment."""
    if not path.is_file():
        return ()
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, raw_value = line.partition("=")
        key = key.strip()
        if not separator or key not in DEEPSEEK_ENV_KEYS or key in os.environ:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)
