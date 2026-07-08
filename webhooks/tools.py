"""Custom functions chamadas pelo agente Retell durante a chamada.

Regra de ouro: responder depressa (<1s) — o cliente está em linha.
O trabalho lento (SMS) vai para background tasks depois da resposta.
"""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from .config import get_settings
from .notify import enviar_sms, texto_sms_urgencia
from .security import retell_auth
from .storage import guardar_recado, guardar_urgencia, marcar_sms_enviado

log = logging.getLogger("voice-onboard.tools")

router = APIRouter(prefix="/retell/tools", dependencies=[Depends(retell_auth)])


async def _payload(request: Request) -> tuple[dict, str]:
    """Extrai (args, call_id) do corpo enviado pela Retell: {name, call, args}."""
    corpo = await request.json()
    args = corpo.get("args") if isinstance(corpo.get("args"), dict) else corpo
    call_id = (corpo.get("call") or {}).get("call_id", "") if isinstance(corpo, dict) else ""
    return args or {}, call_id


async def _notificar_e_marcar(urgencia_id: int, texto: str) -> None:
    settings = get_settings()
    if await enviar_sms(texto):
        await asyncio.to_thread(marcar_sms_enviado, settings.db_path, urgencia_id)


@router.post("/notificar_tecnico")
async def notificar_tecnico(request: Request, tarefas: BackgroundTasks) -> dict:
    args, call_id = await _payload(request)
    nome = args.get("nome", "desconhecido")
    morada = args.get("morada", "por confirmar")
    telemovel = args.get("telemovel", "desconhecido")
    problema = args.get("problema", "não especificado")
    settings = get_settings()
    urgencia_id = await asyncio.to_thread(
        guardar_urgencia, settings.db_path, call_id, nome, morada, telemovel, problema
    )
    tarefas.add_task(
        _notificar_e_marcar,
        urgencia_id,
        texto_sms_urgencia(nome, morada, telemovel, problema),
    )
    log.info("Urgência #%s registada (call %s)", urgencia_id, call_id)
    return {
        "resultado": (
            "O alerta está a ser enviado ao técnico de serviço. O cliente vai ser "
            "contactado no número indicado dentro de quinze a trinta minutos."
        )
    }


@router.post("/registar_recado")
async def registar_recado(request: Request) -> dict:
    args, call_id = await _payload(request)
    settings = get_settings()
    recado_id = await asyncio.to_thread(
        guardar_recado,
        settings.db_path,
        call_id,
        args.get("nome", "desconhecido"),
        args.get("telemovel", "desconhecido"),
        args.get("assunto", "não especificado"),
    )
    log.info("Recado #%s registado (call %s)", recado_id, call_id)
    return {
        "resultado": (
            "Recado registado com sucesso. O cliente será contactado "
            "amanhã de manhã pelo escritório."
        )
    }
