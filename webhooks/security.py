"""Verificação da assinatura X-Retell-Signature.

Esquema do SDK oficial (retell-python-sdk, lib/webhook_auth.py):
assinatura = "v=<timestamp_ms>,d=<hex>" com
hex = HMAC-SHA256(chave=RETELL_API_KEY, mensagem=corpo + str(timestamp_ms)).
A janela de validade do timestamp é de 5 minutos.
"""

import hashlib
import hmac
import re
import time

from fastapi import HTTPException, Request

from .config import get_settings

JANELA_MS = 5 * 60 * 1000
_PADRAO = re.compile(r"v=(\d+),d=(.*)")


def assinar(corpo: str, api_key: str, timestamp_ms: int | None = None) -> str:
    """Gera uma assinatura no formato da Retell (usado nos testes)."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    digest = hmac.new(
        api_key.encode(), (corpo + str(timestamp_ms)).encode(), hashlib.sha256
    ).hexdigest()
    return f"v={timestamp_ms},d={digest}"


def verificar_assinatura(
    corpo: str, api_key: str, assinatura: str, agora_ms: int | None = None
) -> bool:
    match = _PADRAO.search(assinatura or "")
    if not match:
        return False
    timestamp_ms = int(match.group(1))
    digest_recebido = match.group(2)
    if agora_ms is None:
        agora_ms = int(time.time() * 1000)
    if abs(agora_ms - timestamp_ms) > JANELA_MS:
        return False
    esperado = hmac.new(
        api_key.encode(), (corpo + str(timestamp_ms)).encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, digest_recebido)


async def retell_auth(request: Request) -> None:
    """Dependency FastAPI: rejeita pedidos sem assinatura Retell válida."""
    settings = get_settings()
    if not settings.verify_signature:
        return
    # Sem key configurada, uma HMAC de chave vazia seria forjável — rejeitar tudo.
    if not settings.retell_api_key:
        raise HTTPException(status_code=401, detail="RETELL_API_KEY não configurada")
    assinatura = request.headers.get("X-Retell-Signature", "")
    corpo = (await request.body()).decode()
    if not verificar_assinatura(corpo, settings.retell_api_key, assinatura):
        raise HTTPException(status_code=401, detail="Assinatura Retell inválida")
