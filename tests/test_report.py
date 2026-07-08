from webhooks.report import gerar_relatorio
from webhooks.storage import guardar_recado, guardar_urgencia, upsert_chamada


def test_relatorio_agrega_atividade(cliente, db_path):
    guardar_urgencia(
        db_path, "c1", "Maria", "Rua A 1, Lisboa", "+351911111111", "fuga de água"
    )
    guardar_recado(db_path, "c2", "João", "+351922222222", "orçamento pintura")
    upsert_chamada(
        db_path,
        {
            "call_id": "c3",
            "from_number": "+351933333333",
            "call_analysis": {
                "call_summary": "Marcou visita para quinta.",
                "custom_analysis_data": {"tipo_pedido": "marcacao"},
            },
            "call_cost": {"combined_cost": 30.0},
        },
    )
    relatorio = gerar_relatorio(db_path)
    assert "Chamadas atendidas: 1" in relatorio
    assert "Urgências acionadas: 1" in relatorio
    assert "Marcações feitas: 1" in relatorio
    assert "Recados registados: 1" in relatorio
    assert "fuga de água" in relatorio
    assert "orçamento pintura" in relatorio


def test_relatorio_endpoint_exige_token(cliente):
    assert cliente.get("/relatorio/hoje").status_code == 403
    assert cliente.get("/relatorio/hoje?token=errado").status_code == 403
    resposta = cliente.get("/relatorio/hoje?token=token-teste")
    assert resposta.status_code == 200
    assert "Relatório diário" in resposta.json()["relatorio"]


def test_relatorio_aceita_token_por_header(cliente):
    resposta = cliente.get(
        "/relatorio/hoje", headers={"X-Report-Token": "token-teste"}
    )
    assert resposta.status_code == 200
    assert (
        cliente.get("/relatorio/hoje", headers={"X-Report-Token": "errado"}).status_code
        == 403
    )


def test_health(cliente):
    assert cliente.get("/health").json() == {"status": "ok"}
