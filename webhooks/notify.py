"""Envio de SMS via API REST da Twilio (httpx, sem SDK)."""

import logging

import httpx

from .config import get_settings

log = logging.getLogger("voice-onboard.notify")


async def enviar_sms(texto: str, para: str | None = None) -> bool:
    """Envia um SMS ao dono do negócio. Devolve True se a Twilio aceitou."""
    settings = get_settings()
    destino = para or settings.owner_phone
    if not (settings.twilio_account_sid and settings.twilio_auth_token and destino):
        # Não logar o corpo: contém dados pessoais do cliente.
        log.warning("Twilio não configurada — SMS não enviado (%d chars)", len(texto))
        return False
    url = (
        "https://api.twilio.com/2010-04-01/Accounts/"
        f"{settings.twilio_account_sid}/Messages.json"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resposta = await client.post(
                url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={
                    "From": settings.twilio_from_number,
                    "To": destino,
                    "Body": texto,
                },
            )
        if resposta.status_code >= 300:
            log.error("Twilio devolveu %s: %s", resposta.status_code, resposta.text)
            return False
        return True
    except httpx.HTTPError as erro:
        log.error("Falha a contactar a Twilio: %s", erro)
        return False


def texto_sms_urgencia(nome: str, morada: str, telemovel: str, problema: str) -> str:
    settings = get_settings()
    return (
        f"[{settings.business_name}] URGENCIA fora de horas\n"
        f"Cliente: {nome}\n"
        f"Morada: {morada}\n"
        f"Contacto: {telemovel}\n"
        f"Problema: {problema}\n"
        "Ligar ao cliente em 15-30 min."
    )
