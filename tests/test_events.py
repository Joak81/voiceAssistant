import json
import sqlite3

from tests.conftest import TEST_API_KEY
from webhooks.security import assinar


def _evento(call_id: str, evento: str, **extra) -> dict:
    return {"event": evento, "call": {"call_id": call_id, **extra}}


def _post(cliente, payload: dict):
    corpo = json.dumps(payload)
    return cliente.post(
        "/retell/webhook",
        content=corpo,
        headers={
            "Content-Type": "application/json",
            "X-Retell-Signature": assinar(corpo, TEST_API_KEY),
        },
    )


def test_call_analyzed_grava_resumo_e_custo(cliente, db_path):
    payload = _evento(
        "call_123",
        "call_analyzed",
        from_number="+351911222333",
        to_number="+14155550100",
        start_timestamp=1751964000000,
        end_timestamp=1751964180000,
        duration_ms=180000,
        transcript="Agent: Boa noite...",
        call_analysis={
            "call_summary": "Cliente reportou torneira a pingar; ficou recado.",
            "user_sentiment": "Neutral",
            "call_successful": True,
            "in_voicemail": False,
            "custom_analysis_data": {"tipo_pedido": "recado"},
        },
        call_cost={"combined_cost": 45.0, "total_duration_seconds": 180},
    )
    resposta = _post(cliente, payload)
    assert resposta.status_code == 200

    linha = (
        sqlite3.connect(db_path)
        .execute("SELECT resumo, tipo_pedido, custo_usd FROM chamadas")
        .fetchone()
    )
    assert "torneira" in linha[0]
    assert linha[1] == "recado"
    assert abs(linha[2] - 0.45) < 1e-9


def test_call_started_depois_analyzed_nao_apaga(cliente, db_path):
    _post(cliente, _evento("call_9", "call_analyzed",
                           call_analysis={"call_summary": "resumo final"}))
    # um evento tardio sem análise não deve limpar o resumo
    _post(cliente, _evento("call_9", "call_ended", duration_ms=60000))
    linha = (
        sqlite3.connect(db_path)
        .execute("SELECT resumo, duration_ms FROM chamadas WHERE call_id='call_9'")
        .fetchone()
    )
    assert linha[0] == "resumo final"
    assert linha[1] == 60000


def test_evento_desconhecido_ignorado(cliente):
    resposta = _post(cliente, {"event": "outra_coisa", "call": {}})
    assert resposta.status_code == 200
