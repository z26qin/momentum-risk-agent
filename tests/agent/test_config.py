from __future__ import annotations

from src.agent.config import (
    LANGSMITH_ENV_KEYS,
    load_deepseek_env,
    load_langsmith_env,
    load_local_env,
)


def _make_env_key_absent(monkeypatch, key: str) -> None:
    monkeypatch.setenv(key, "__test_cleanup_sentinel__")
    monkeypatch.delenv(key)


def test_load_deepseek_env_reads_quoted_values(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'DEEPSEEK_API_KEY=""\n'
        'DEEPSEEK_MODEL="deepseek-v4-pro"\n'
        "DEEPSEEK_BASE_URL=https://api.deepseek.com\n"
        "UNRELATED=value\n",
        encoding="utf-8",
    )
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"):
        _make_env_key_absent(monkeypatch, key)

    loaded = load_deepseek_env(env_file)

    assert loaded == (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
    )
    assert __import__("os").environ["DEEPSEEK_API_KEY"] == ""
    assert __import__("os").environ["DEEPSEEK_MODEL"] == "deepseek-v4-pro"
    assert __import__("os").environ["DEEPSEEK_BASE_URL"] == "https://api.deepseek.com"
    assert "UNRELATED" not in __import__("os").environ


def test_load_deepseek_env_does_not_override_process_environment(
    tmp_path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('DEEPSEEK_API_KEY="file-key"\n', encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "process-key")

    loaded = load_deepseek_env(env_file)

    assert loaded == ()
    assert __import__("os").environ["DEEPSEEK_API_KEY"] == "process-key"


def test_load_deepseek_env_is_optional(tmp_path) -> None:
    assert load_deepseek_env(tmp_path / "missing.env") == ()


def test_load_langsmith_env_reads_new_and_legacy_keys(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'LANGSMITH_TRACING="true"\n'
        'LANGSMITH_API_KEY="ls-test"\n'
        "LANGCHAIN_PROJECT=from-file\n"
        "UNRELATED=value\n",
        encoding="utf-8",
    )
    for key in LANGSMITH_ENV_KEYS:
        _make_env_key_absent(monkeypatch, key)

    loaded = load_langsmith_env(env_file)

    assert loaded == (
        "LANGSMITH_TRACING",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_PROJECT",
    )
    assert __import__("os").environ["LANGSMITH_API_KEY"] == "ls-test"
    assert __import__("os").environ["LANGCHAIN_PROJECT"] == "from-file"
    assert "UNRELATED" not in __import__("os").environ


def test_load_langsmith_env_defaults_project_when_tracing(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LANGSMITH_TRACING=true\nLANGSMITH_API_KEY=ls-test\n",
        encoding="utf-8",
    )
    for key in LANGSMITH_ENV_KEYS:
        _make_env_key_absent(monkeypatch, key)

    loaded = load_langsmith_env(env_file)

    assert "LANGSMITH_PROJECT" in loaded
    assert __import__("os").environ["LANGSMITH_PROJECT"] == "momentum-risk-agent"


def test_load_local_env_loads_both_allowlists(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'DEEPSEEK_API_KEY="ds"\nLANGSMITH_TRACING=false\n',
        encoding="utf-8",
    )
    _make_env_key_absent(monkeypatch, "DEEPSEEK_API_KEY")
    for key in LANGSMITH_ENV_KEYS:
        _make_env_key_absent(monkeypatch, key)

    loaded = load_local_env(env_file)

    assert "DEEPSEEK_API_KEY" in loaded
    assert "LANGSMITH_TRACING" in loaded
    assert __import__("os").environ["DEEPSEEK_API_KEY"] == "ds"

