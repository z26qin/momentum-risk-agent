from __future__ import annotations

from src.agent.config import load_deepseek_env


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
