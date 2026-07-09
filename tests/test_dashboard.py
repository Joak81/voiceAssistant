import time

from webhooks.storage import guardar_recado, guardar_urgencia, upsert_chamada


def test_dashboard_exige_token(cliente):
    assert cliente.get("/dashboard").status_code == 403
    assert cliente.get("/dashboard?token=errado").status_code == 403


def test_dashboard_mostra_atividade(cliente, db_path, monkeypatch):
    # sem Cal.com configurado a secção de marcações degrada graciosamente
    guardar_urgencia(db_path, "c1", "Maria", "Rua A 1", "+351911111111", "fuga de água")
    guardar_recado(db_path, "c2", "João <b>", "+351922222222", "orçamento pintura")
    upsert_chamada(
        db_path,
        {
            "call_id": "c3",
            "from_number": "+351933333333",
            "start_timestamp": int(time.time() * 1000) - 3_600_000,
            "duration_ms": 95000,
            "transcript": "Agent: Boa noite <script>alert(1)</script>",
            "call_analysis": {
                "call_summary": "Pediu contacto amanhã.",
                "custom_analysis_data": {"tipo_pedido": "recado"},
            },
        },
    )
    resposta = cliente.get("/dashboard?token=token-teste")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "fuga de água" in corpo
    assert "orçamento pintura" in corpo
    assert "Pediu contacto amanhã." in corpo
    # conteúdo vindo de conversas tem de sair escapado
    assert "<script>" not in corpo
    assert "&lt;script&gt;" in corpo
    assert "João &lt;b&gt;" in corpo
    # sem key do Cal.com: mensagem de vazio, sem rebentar
    assert "Sem marcações" in corpo
