import pytest

from resistance.config import load_settings


def test_loads_required_bot_token_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "bot.db"))

    settings = load_settings()

    assert settings.bot_token == "token"
    assert settings.database_path == tmp_path / "bot.db"


def test_rejects_missing_bot_token(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        load_settings()
