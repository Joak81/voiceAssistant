import json
import sqlite3

import webhooks.grok_llm as grok


def _delta_conteudo(texto, fim=None):
    escolha = {"delta": {"content": texto}}
    if fim:
        escolha["finish_reason"] = fim
    return {"choices": [escolha]}


def _delta_tool(nome, argumentos):
    return {"choices": [{"delta": {"tool_calls": [{
        "index": 0, "id": "call_1",
        "function": {"name": nome, "arguments": json.dumps(argumentos)},
    }]}}]}


def _fim(razao):
    return {"choices": [{"delta": {}, "finish_reason": razao}]}


def test_handshake_config_e_abertura(cliente):
    with cliente.websocket_connect("/llm-websocket/call_ws1") as ws:
        config = ws.receive_json()
        assert config["response_type"] == "config"
        assert config["config"]["call_details"] is True

        ws.send_json({"interaction_type": "call_details", "call": {"call_id": "call_ws1"}})
        abertura = ws.receive_json()
        assert abertura["response_id"] == 0
        assert "assistente virtual" in abertura["content"]
        assert "inteligência artificial" in abertura["content"]
        assert abertura["content_complete"] is True


def test_reconexao_nao_repete_abertura(cliente):
    # 1.ª ligação: abertura enviada
    with cliente.websocket_connect("/llm-websocket/call_reconn") as ws:
        ws.receive_json()  # config
        ws.send_json({"interaction_type": "call_details", "call": {}})
        assert "assistente virtual" in ws.receive_json()["content"]
    # reconexão (auto_reconnect): call_details repetido NÃO pode reapresentar
    with cliente.websocket_connect("/llm-websocket/call_reconn") as ws:
        ws.receive_json()  # config
        ws.send_json({"interaction_type": "call_details", "call": {}})
        ws.send_json({"interaction_type": "ping_pong", "timestamp": 7})
        proximo = ws.receive_json()
        assert proximo == {"response_type": "ping_pong", "timestamp": 7}


def test_ping_pong(cliente):
    with cliente.websocket_connect("/llm-websocket/call_ws2") as ws:
        ws.receive_json()  # config
        ws.send_json({"interaction_type": "ping_pong", "timestamp": 12345})
        eco = ws.receive_json()
        assert eco == {"response_type": "ping_pong", "timestamp": 12345}


def test_response_required_faz_stream(cliente, monkeypatch):
    async def stream_falso(messages, tools):
        assert messages[0]["role"] == "system"
        assert "Arranjos Horizonte" in messages[0]["content"]
        yield _delta_conteudo("Boa ")
        yield _delta_conteudo("noite.", fim="stop")

    monkeypatch.setattr(grok, "_stream_xai", stream_falso)
    with cliente.websocket_connect("/llm-websocket/call_ws3") as ws:
        ws.receive_json()  # config
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 3,
            "transcript": [{"role": "user", "content": "Olá?"}],
        })
        partes, completo = [], False
        while not completo:
            m = ws.receive_json()
            assert m["response_id"] == 3
            partes.append(m["content"])
            completo = m["content_complete"]
        assert "".join(partes) == "Boa noite."


def test_tool_registar_recado_grava_e_fala(cliente, db_path, monkeypatch):
    chamadas = {"n": 0}

    async def stream_falso(messages, tools):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            yield _delta_tool("registar_recado", {
                "nome": "Rui", "telemovel": "+351911222333",
                "assunto": "orçamento estores",
            })
            yield _fim("tool_calls")
        else:
            # o resultado do tool tem de estar no contexto da 2.ª ronda
            assert any(m.get("role") == "tool" for m in messages)
            yield _delta_conteudo("Está registado. Será contactado amanhã.", fim="stop")

    monkeypatch.setattr(grok, "_stream_xai", stream_falso)
    with cliente.websocket_connect("/llm-websocket/call_ws4") as ws:
        ws.receive_json()  # config
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 1,
            "transcript": [{"role": "user", "content": "Liguem-me amanhã"}],
        })
        partes, completo = [], False
        while not completo:
            m = ws.receive_json()
            partes.append(m["content"])
            completo = m["content_complete"]
        assert "registado" in "".join(partes).lower()

    linhas = sqlite3.connect(db_path).execute(
        "SELECT nome, assunto FROM recados WHERE call_id='call_ws4'").fetchall()
    assert linhas == [("Rui", "orçamento estores")]


def test_terminar_chamada_envia_end_call(cliente, monkeypatch):
    async def stream_falso(messages, tools):
        yield _delta_tool("terminar_chamada", {})
        yield _fim("tool_calls")

    monkeypatch.setattr(grok, "_stream_xai", stream_falso)
    with cliente.websocket_connect("/llm-websocket/call_ws5") as ws:
        ws.receive_json()  # config
        ws.send_json({
            "interaction_type": "response_required",
            "response_id": 2,
            "transcript": [{"role": "user", "content": "adeus"}],
        })
        m = ws.receive_json()
        assert m["end_call"] is True
        assert m["content_complete"] is True
