"""Leitura das marcações reais no Cal.com (para o dashboard)."""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from .config import get_settings

log = logging.getLogger("voice-onboard.calcom")


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
