"""Webhook de eventos de chamada da Retell (call_started/call_ended/call_analyzed).

A Retell espera 2xx em <10s; gravamos e devolvemos já.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Request

from .config import get_settings
from .security import retell_auth
from .storage import upsert_chamada

log = logging.getLogger("voice-onboard.events")

router = APIRouter(dependencies=[Depends(retell_auth)])


@router.post("/retell/webhook")
async def webhook_chamadas(request: Request) -> dict:
    corpo = await request.json()
    evento = corpo.get("event", "")
    call = corpo.get("call") or {}
    if evento in ("call_started", "call_ended", "call_analyzed"):
        settings = get_settings()
        await asyncio.to_thread(upsert_chamada, settings.db_path, call)
        log.info("Evento %s da chamada %s gravado", evento, call.get("call_id"))
    else:
        log.info("Evento ignorado: %s", evento)
    return {"ok": True}
