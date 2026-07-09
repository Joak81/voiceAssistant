import json
import sqlite3

from tests.conftest import TEST_API_KEY
from webhooks.security import assinar


def _post_assinado(cliente, caminho: str, payload: dict):
    corpo = json.dumps(payload)
    return cliente.post(
        caminho,
        content=corpo,
        headers={
            "Content-Type": "application/json",
            "X-Retell-Signature": assinar(corpo, TEST_API_KEY),
        },
    )


def test_rejeita_sem_assinatura(cliente):
    resposta = cliente.post("/retell/tools/notificar_tecnico", json={"args": {}})
    assert resposta.status_code == 401


def test_rejeita_assinatura_invalida(cliente):
    resposta = cliente.post(
        "/retell/tools/notificar_tecnico",
        content="{}",
        headers={"X-Retell-Signature": "v=1,d=abc"},
    )
    assert resposta.status_code == 401


def test_rejeita_tudo_sem_api_key_configurada(cliente, monkeypatch):
    # com a key vazia, nem uma assinatura "válida" de chave vazia pode passar
    from webhooks.config import get_settings

    monkeypatch.setenv("RETELL_API_KEY", "")
    get_settings.cache_clear()
    corpo = "{}"
    resposta = cliente.post(
        "/retell/tools/registar_recado",
        content=corpo,
        headers={"X-Retell-Signature": assinar(corpo, "")},
    )
    assert resposta.status_code == 401
    monkeypatch.setenv("RETELL_API_KEY", TEST_API_KEY)
    get_settings.cache_clear()


def test_notificar_tecnico_grava_urgencia(cliente, db_path, monkeypatch):
    enviados = []

    async def sms_falso(texto, para=None):
        enviados.append(texto)
        return True

    import webhooks.tools as tools

    monkeypatch.setattr(tools, "enviar_sms", sms_falso)

    payload = {
        "name": "notificar_tecnico",
        "call": {"call_id": "call_abc"},
        "args": {
            "nome": "Maria Silva",
            "morada": "Rua das Flores 12, 2E, Lisboa",
            "telemovel": "+351912345678",
            "problema": "cano rebentado na cozinha",
        },
    }
    resposta = _post_assinado(cliente, "/retell/tools/notificar_tecnico", payload)
    assert resposta.status_code == 200
    assert "técnico" in resposta.json()["resultado"]

    linhas = sqlite3.connect(db_path).execute("SELECT * FROM urgencias").fetchall()
    assert len(linhas) == 1
    assert "Maria Silva" in linhas[0]
    # o SMS segue em background task (executa antes do TestClient devolver)
    assert len(enviados) == 1
    assert "cano rebentado" in enviados[0]


def test_sms_urgencia_compacto_sem_acentos(cliente):
    from webhooks.notify import texto_sms_urgencia

    texto = texto_sms_urgencia(
        nome="José Antão de Sousa e Melo da Câmara Pereira",
        morada="Avenida General Humberto Delgado, número çento e vinte e três, "
               "quarto esquerdo, São João da Talha, Loures",
        telemovel="+351919000957",
        problema="fuga de água no aquecedor çentral com inundação da cozinha "
                 "e infiltração no teto do vizinho de baixo",
    )
    assert texto.isascii(), "acentos forçam UCS-2 e rebentam o limite da trial"
    assert len(texto) <= 210, f"SMS com {len(texto)} chars excede 2 segmentos GSM-7"
    assert "URGENTE" in texto and "+351919000957" in texto


def test_registar_recado(cliente, db_path):
    payload = {
        "name": "registar_recado",
        "call": {"call_id": "call_def"},
        "args": {
            "nome": "João Costa",
            "telemovel": "+351961111222",
            "assunto": "orçamento para pintura da sala",
        },
    }
    resposta = _post_assinado(cliente, "/retell/tools/registar_recado", payload)
    assert resposta.status_code == 200
    linhas = sqlite3.connect(db_path).execute("SELECT * FROM recados").fetchall()
    assert len(linhas) == 1
    assert "João Costa" in linhas[0]
