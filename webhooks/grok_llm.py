"""Motor Custom LLM da Retell com Grok (xAI) — WebSocket /llm-websocket/{call_id}.

Protocolo (demo oficial RetellAI/retell-custom-llm-python-demo):
  Retell → nós: ping_pong | call_details | update_only |
                response_required/reminder_required {response_id, transcript}
  nós → Retell: config | ping_pong | response {response_id, content,
                content_complete, end_call}

Os tools correm neste processo (storage/notify/calcom) — sem webhooks HTTP.
"""

import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .calcom import criar_marcacao, slots_livres
from .config import get_settings
from .notify import enviar_sms, texto_sms_urgencia
from .prompt_loader import carregar_prompt
from .storage import guardar_recado, guardar_urgencia, marcar_sms_enviado

log = logging.getLogger("voice-onboard.grok")

router = APIRouter()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "notificar_tecnico",
            "description": "Envia SMS de alerta ao técnico de serviço com os dados da urgência. Chamar apenas em urgências, depois de recolher nome, morada e telemóvel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "morada": {"type": "string"},
                    "telemovel": {"type": "string"},
                    "problema": {"type": "string"},
                },
                "required": ["nome", "morada", "telemovel", "problema"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registar_recado",
            "description": "Regista um recado para o escritório contactar o cliente na manhã seguinte. Usar sempre que prometeres que o cliente vai ser contactado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "telemovel": {"type": "string"},
                    "assunto": {"type": "string"},
                },
                "required": ["nome", "telemovel", "assunto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_agenda",
            "description": "Consulta os próximos horários livres na agenda para propor ao cliente (máximo duas opções de cada vez).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_servico",
            "description": "Marca a visita num dos horários devolvidos por consultar_agenda. Usar o campo iso exato do slot escolhido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inicio_iso": {"type": "string", "description": "campo iso do slot"},
                    "nome": {"type": "string"},
                    "telemovel": {"type": "string"},
                    "assunto": {"type": "string"},
                },
                "required": ["inicio_iso", "nome", "telemovel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminar_chamada",
            "description": "Termina a chamada depois da frase de despedida.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


async def _executar_tool(nome: str, args: dict, call_id: str) -> tuple[str, bool]:
    """Executa um tool. Devolve (resultado_para_o_llm, terminar_chamada)."""
    settings = get_settings()
    if nome == "notificar_tecnico":
        urgencia_id = await asyncio.to_thread(
            guardar_urgencia, settings.db_path, call_id,
            args.get("nome", "?"), args.get("morada", "?"),
            args.get("telemovel", "?"), args.get("problema", "?"),
        )

        async def _sms():
            texto = texto_sms_urgencia(args.get("nome", "?"), args.get("morada", "?"),
                                       args.get("telemovel", "?"), args.get("problema", "?"))
            if await enviar_sms(texto):
                await asyncio.to_thread(marcar_sms_enviado, settings.db_path, urgencia_id)

        asyncio.create_task(_sms())
        return ("Alerta a caminho do técnico de serviço. Confirma ao cliente que será "
                "contactado em 15 a 30 minutos.", False)
    if nome == "registar_recado":
        await asyncio.to_thread(
            guardar_recado, settings.db_path, call_id,
            args.get("nome", "?"), args.get("telemovel", "?"), args.get("assunto", "?"),
        )
        return ("Recado registado. Confirma ao cliente que será contactado amanhã "
                "de manhã.", False)
    if nome == "consultar_agenda":
        slots = await slots_livres()
        if not slots:
            return ("Sem vagas disponíveis nos próximos dias. Propõe registar recado "
                    "para o escritório combinar diretamente.", False)
        return (json.dumps({"slots": slots}, ensure_ascii=False), False)
    if nome == "marcar_servico":
        resultado = await criar_marcacao(
            args.get("inicio_iso", ""), args.get("nome", "?"),
            args.get("telemovel", "?"), args.get("assunto", ""),
        )
        if resultado["ok"]:
            return ("Marcação criada com sucesso. Confirma dia, hora e morada em voz "
                    "alta ao cliente.", False)
        return (f"Falhou: {resultado['detalhe']}. Propõe outro horário ou registar "
                "recado.", False)
    if nome == "terminar_chamada":
        return ("", True)
    return (f"tool desconhecido: {nome}", False)


async def _stream_xai(messages: list[dict], tools: list[dict]):
    """Stream de chat completions da xAI. Gera dicts delta do formato OpenAI."""
    settings = get_settings()
    corpo = {
        "model": settings.grok_model,
        "messages": messages,
        "tools": tools,
        "stream": True,
        "temperature": 0.3,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream(
            "POST", "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.xai_api_key}"},
            json=corpo,
        ) as resposta:
            if resposta.status_code >= 300:
                detalhe = (await resposta.aread()).decode()[:200]
                raise RuntimeError(f"xAI {resposta.status_code}: {detalhe}")
            async for linha in resposta.aiter_lines():
                if not linha.startswith("data: "):
                    continue
                dado = linha[6:]
                if dado.strip() == "[DONE]":
                    return
                yield json.loads(dado)


def _mensagens(transcript: list[dict], system_prompt: str) -> list[dict]:
    papel = {"agent": "assistant", "user": "user", "system": "user"}
    msgs = [{"role": "system", "content": system_prompt}]
    for u in transcript:
        msgs.append({"role": papel.get(u.get("role"), "user"), "content": u.get("content", "")})
    return msgs


class _Sessao:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.ultimo_response_id = -1
        self.tarefa: asyncio.Task | None = None


async def _responder(ws: WebSocket, sessao: _Sessao, response_id: int,
                     transcript: list[dict]) -> None:
    system_prompt, _ = carregar_prompt()
    messages = _mensagens(transcript, system_prompt)

    async def enviar(conteudo: str, completo: bool, end_call: bool = False) -> None:
        if response_id < sessao.ultimo_response_id:
            raise asyncio.CancelledError  # resposta obsoleta: o cliente interrompeu
        await ws.send_json({
            "response_type": "response",
            "response_id": response_id,
            "content": conteudo,
            "content_complete": completo,
            "end_call": end_call,
        })

    try:
        # até 3 rondas de tool calling
        for _ in range(3):
            texto_enviado = False
            tool_calls: dict[int, dict] = {}
            fim = None
            async for pedaco in _stream_xai(messages, TOOLS):
                escolha = (pedaco.get("choices") or [{}])[0]
                delta = escolha.get("delta") or {}
                if delta.get("content"):
                    texto_enviado = True
                    await enviar(delta["content"], False)
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    atual = tool_calls.setdefault(
                        idx, {"id": "", "function": {"name": "", "arguments": ""}})
                    if tc.get("id"):
                        atual["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        atual["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        atual["function"]["arguments"] += fn["arguments"]
                if escolha.get("finish_reason"):
                    fim = escolha["finish_reason"]

            if fim != "tool_calls" or not tool_calls:
                await enviar("", True)
                return

            # executar tools e voltar ao modelo para a frase falada
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": t["id"] or f"call_{i}", "type": "function", "function": t["function"]}
                    for i, t in sorted(tool_calls.items())
                ],
            })
            for i, t in sorted(tool_calls.items()):
                nome = t["function"]["name"]
                try:
                    args = json.loads(t["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                resultado, terminar = await _executar_tool(nome, args, sessao.call_id)
                log.info("call %s: tool %s executado", sessao.call_id, nome)
                if terminar:
                    await enviar("Obrigada pela sua chamada. Boa noite.", True, end_call=True)
                    return
                messages.append({
                    "role": "tool",
                    "tool_call_id": t["id"] or f"call_{i}",
                    "content": resultado,
                })
        await enviar("", True)
    except asyncio.CancelledError:
        raise
    except Exception as erro:  # falha da xAI/rede: não deixar o cliente em silêncio
        log.error("call %s: motor falhou: %s", sessao.call_id, erro)
        try:
            await enviar(
                "Peço desculpa, tive uma dificuldade técnica. Pode repetir, por favor?",
                True,
            )
        except Exception:
            pass


@router.websocket("/llm-websocket/{call_id}")
async def llm_websocket(ws: WebSocket, call_id: str) -> None:
    await ws.accept()
    sessao = _Sessao(call_id)
    _, abertura = carregar_prompt()
    await ws.send_json({
        "response_type": "config",
        "config": {"auto_reconnect": True, "call_details": True},
    })
    log.info("call %s: websocket ligado (motor Grok)", call_id)
    try:
        while True:
            pedido = await ws.receive_json()
            tipo = pedido.get("interaction_type")
            if tipo == "ping_pong":
                await ws.send_json({"response_type": "ping_pong",
                                    "timestamp": pedido.get("timestamp")})
            elif tipo == "call_details":
                await ws.send_json({
                    "response_type": "response",
                    "response_id": 0,
                    "content": abertura,
                    "content_complete": True,
                    "end_call": False,
                })
            elif tipo in ("response_required", "reminder_required"):
                response_id = pedido.get("response_id", 0)
                sessao.ultimo_response_id = max(sessao.ultimo_response_id, response_id)
                if sessao.tarefa and not sessao.tarefa.done():
                    sessao.tarefa.cancel()
                sessao.tarefa = asyncio.create_task(
                    _responder(ws, sessao, response_id, pedido.get("transcript") or [])
                )
            # update_only: transcript intermédio — nada a fazer
    except WebSocketDisconnect:
        log.info("call %s: websocket terminado", call_id)
    finally:
        if sessao.tarefa and not sessao.tarefa.done():
            sessao.tarefa.cancel()
