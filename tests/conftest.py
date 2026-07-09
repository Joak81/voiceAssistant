import os

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "key_teste_1234567890"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """TestClient com BD temporária e assinatura Retell ativa."""
    monkeypatch.setenv("RETELL_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("VERIFY_SIGNATURE", "true")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("REPORT_TOKEN", "token-teste")
    monkeypatch.setenv("BUSINESS_NAME", "Arranjos Horizonte")
    # Sem credenciais externas nos testes. setenv("") em vez de delenv:
    # um .env real na raiz seria lido pelo pydantic-settings, e as env vars
    # (mesmo vazias) têm prioridade sobre o ficheiro.
    for var in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_NUMBER",
        "OWNER_PHONE",
        "GMAIL_USER",
        "GMAIL_APP_PASSWORD",
        "OWNER_EMAIL",
        "CALCOM_API_KEY",
        "WEBHOOK_BASE_URL",
        "RAILWAY_TOKEN",
    ):
        monkeypatch.setenv(var, "")

    from webhooks.config import get_settings

    get_settings.cache_clear()
    from webhooks.main import app

    with TestClient(app) as tc:
        yield tc
    get_settings.cache_clear()


@pytest.fixture
def db_path():
    from webhooks.config import get_settings

    return get_settings().db_path
