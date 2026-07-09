"""Envio de SMS via API REST da Twilio (httpx, sem SDK)."""

import logging
import unicodedata

import httpx

from .config import get_settings

log = logging.getLogger("voice-onboard.notify")


def _ascii(texto: str, maximo: int) -> str:
    """Translitera para ASCII (á→a, ç→c) e trunca — mantém o SMS em GSM-7.

    Acentos forçam UCS-2 (70 chars/segmento em vez de 160) e a trial da
    Twilio rejeita mensagens com demasiados segmentos (erro 30044).
    """
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    plano = " ".join(plano.split())
    return plano[: maximo - 1] + "." if len(plano) > maximo else plano


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
    """SMS compacto (<=210 chars, ASCII) — cabe em 2 segmentos mesmo em trial."""
    settings = get_settings()
    return (
        f"URGENTE {_ascii(settings.business_name, 24)}: "
        f"{_ascii(nome, 30)} | {_ascii(telemovel, 17)} | "
        f"{_ascii(problema, 50)} | {_ascii(morada, 50)} | Ligar 15-30min"
    )
