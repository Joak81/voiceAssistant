"""Integração Cal.com: marcações para o dashboard e tools do motor Grok."""

import logging
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .config import get_settings

log = logging.getLogger("voice-onboard.calcom")

_DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


async def slots_livres(dias: int = 7, maximo: int = 4) -> list[dict]:
    """Próximos slots livres do event type, formatados para fala em PT."""
    settings = get_settings()
    if not (settings.calcom_api_key and settings.calcom_event_type_id):
        return []
    inicio = datetime.now(UTC) + timedelta(hours=1)
    fim = inicio + timedelta(days=dias)
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.cal.com/v2/slots",
                headers={
                    "Authorization": f"Bearer {settings.calcom_api_key}",
                    "cal-api-version": "2024-09-04",
                },
                params={
                    "eventTypeId": settings.calcom_event_type_id,
                    "start": inicio.strftime("%Y-%m-%d"),
                    "end": fim.strftime("%Y-%m-%d"),
                    "timeZone": settings.timezone,
                },
            )
        if r.status_code >= 300:
            log.warning("Cal.com slots devolveu %s: %s", r.status_code, r.text[:120])
            return []
        dados = r.json().get("data", {})
    except httpx.HTTPError as erro:
        log.warning("Cal.com slots inacessível: %s", erro)
        return []
    slots = []
    for dia in sorted(dados):
        for s in dados[dia]:
            try:
                dt = datetime.fromisoformat(s["start"])
            except (KeyError, ValueError):
                continue
            slots.append({
                "iso": s["start"],
                "descricao": f"{_DIAS_PT[dt.weekday()]} dia {dt.day} às {dt.strftime('%H:%M')}",
            })
            if len(slots) >= maximo:
                return slots
    return slots


async def criar_marcacao(inicio_iso: str, nome: str, telemovel: str, assunto: str = "") -> dict:
    """Cria o booking no Cal.com. Devolve {ok, detalhe}."""
    settings = get_settings()
    digitos = re.sub(r"\D", "", telemovel) or "000000000"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://api.cal.com/v2/bookings",
                headers={
                    "Authorization": f"Bearer {settings.calcom_api_key}",
                    "cal-api-version": "2024-08-13",
                },
                json={
                    "start": inicio_iso,
                    "eventTypeId": settings.calcom_event_type_id,
                    "attendee": {
                        "name": nome,
                        "timeZone": settings.timezone,
                        # o cliente dá telefone, não email — email sintético rastreável
                        "email": f"cliente.{digitos}@arranjos-demo.pt",
                        "phoneNumber": telemovel if telemovel.startswith("+") else f"+351{digitos}",
                    },
                    "metadata": {"assunto": assunto[:180]} if assunto else {},
                },
            )
        if r.status_code >= 300:
            log.warning("Cal.com booking falhou %s: %s", r.status_code, r.text[:200])
            return {"ok": False, "detalhe": "não foi possível marcar este horário"}
        return {"ok": True, "detalhe": "marcação criada"}
    except httpx.HTTPError as erro:
        log.warning("Cal.com booking inacessível: %s", erro)
        return {"ok": False, "detalhe": "agenda indisponível de momento"}


async def listar_marcacoes(maximo: int = 12) -> list[dict]:
    """Devolve as próximas/últimas marcações do Cal.com (lista vazia se falhar)."""
    settings = get_settings()
    if not settings.calcom_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.cal.com/v2/bookings",
                headers={
                    "Authorization": f"Bearer {settings.calcom_api_key}",
                    "cal-api-version": "2024-08-13",
                },
                params={"take": maximo, "sortStart": "desc"},
            )
        if r.status_code >= 300:
            log.warning("Cal.com devolveu %s", r.status_code)
            return []
        dados = r.json().get("data", [])
    except httpx.HTTPError as erro:
        log.warning("Cal.com inacessível: %s", erro)
        return []

    fuso = ZoneInfo(settings.timezone)
    marcacoes = []
    for b in dados:
        inicio_raw = b.get("start")
        try:
            inicio = datetime.fromisoformat(inicio_raw.replace("Z", "+00:00"))
            inicio_local = inicio.astimezone(fuso)
            futura = inicio > datetime.now(UTC)
        except (ValueError, AttributeError):
            inicio_local, futura = None, False
        att = (b.get("attendees") or [{}])[0]
        marcacoes.append(
            {
                "quando": inicio_local.strftime("%a %d/%m %H:%M") if inicio_local else "?",
                "futura": futura,
                "titulo": b.get("title") or "",
                "nome": att.get("name") or "?",
                "contacto": att.get("phoneNumber") or att.get("email") or "",
                "estado": b.get("status") or "",
            }
        )
    return marcacoes
