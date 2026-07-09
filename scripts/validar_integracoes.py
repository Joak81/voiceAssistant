"""Pré-verificação das integrações da POC (Fase 2, antes de criar o agente).

Uso:
    uv run python scripts/validar_integracoes.py

Lê o .env da raiz e testa, uma a uma: Retell, Twilio (conta, número, números
verificados), Cal.com (slots do event type), Railway (/health) e Gmail SMTP.
Não cria nem altera nada — só leituras e um login SMTP.
"""

import os
import smtplib
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent


def carregar_env() -> None:
    env = RAIZ / ".env"
    if not env.exists():
        sys.exit("ERRO: falta o .env na raiz (copiar de .env.example)")
    for linha in env.read_text().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))


RESULTADOS: list[tuple[str, bool, str]] = []


def registo(nome: str, ok: bool, detalhe: str) -> None:
    RESULTADOS.append((nome, ok, detalhe))
    print(f"{'✓' if ok else '✗'} {nome}: {detalhe}")


def testar_retell() -> None:
    key = os.environ.get("RETELL_API_KEY", "")
    if not key:
        return registo("Retell", False, "RETELL_API_KEY vazia no .env")
    r = httpx.post(
        "https://api.retellai.com/v2/list-agents",
        headers={"Authorization": f"Bearer {key}"},
        json={},
        timeout=20,
    )
    if r.status_code >= 300:
        return registo("Retell", False, f"API respondeu {r.status_code}: {r.text[:120]}")
    corpo = r.json()
    agentes = corpo if isinstance(corpo, list) else corpo.get("agents", corpo)
    registo("Retell", True, f"key válida ({len(agentes) if isinstance(agentes, list) else '?'} agentes na conta)")


def testar_twilio() -> None:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not (sid and token):
        return registo("Twilio", False, "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN vazios")
    base = f"https://api.twilio.com/2010-04-01/Accounts/{sid}"
    auth = (sid, token)
    conta = httpx.get(f"{base}.json", auth=auth, timeout=20)
    if conta.status_code >= 300:
        return registo("Twilio", False, f"credenciais rejeitadas ({conta.status_code})")
    info = conta.json()
    registo("Twilio", True, f"conta {info.get('status')} (tipo {info.get('type')})")

    numeros = httpx.get(f"{base}/IncomingPhoneNumbers.json", auth=auth, timeout=20).json()
    lista = numeros.get("incoming_phone_numbers", [])
    if lista:
        numero = lista[0]["phone_number"]
        registo("Twilio número", True, f"{numero} — usar como TWILIO_FROM_NUMBER")
        if not os.environ.get("TWILIO_FROM_NUMBER"):
            print(f"  → preenche no .env: TWILIO_FROM_NUMBER={numero}")
    else:
        registo("Twilio número", False,
                "sem números na conta — obter um em Phone Numbers na consola")

    verificados = httpx.get(f"{base}/OutgoingCallerIds.json", auth=auth, timeout=20).json()
    ids = [c["phone_number"] for c in verificados.get("outgoing_caller_ids", [])]
    dono = os.environ.get("OWNER_PHONE", "")
    if info.get("type") == "Trial":
        if dono and dono in ids:
            registo("Twilio verificação", True, f"{dono} está verificado (trial ok)")
        else:
            registo("Twilio verificação", False,
                    f"OWNER_PHONE {dono or '(vazio)'} não está nos verificados {ids} — "
                    "em trial o SMS só chega a números verificados")


def testar_calcom() -> None:
    key = os.environ.get("CALCOM_API_KEY", "")
    event_type = os.environ.get("CALCOM_EVENT_TYPE_ID", "")
    if not (key and event_type):
        return registo("Cal.com", False, "CALCOM_API_KEY/CALCOM_EVENT_TYPE_ID vazios")
    inicio = date.today() + timedelta(days=1)
    fim = inicio + timedelta(days=7)
    r = httpx.get(
        "https://api.cal.com/v2/slots",
        headers={"Authorization": f"Bearer {key}", "cal-api-version": "2024-09-04"},
        params={
            "eventTypeId": event_type,
            "start": inicio.isoformat(),
            "end": fim.isoformat(),
            "timeZone": "Europe/Lisbon",
        },
        timeout=20,
    )
    if r.status_code >= 300:
        return registo("Cal.com", False, f"API respondeu {r.status_code}: {r.text[:160]}")
    dias = r.json().get("data", {})
    n_slots = sum(len(v) for v in dias.values()) if isinstance(dias, dict) else 0
    if n_slots:
        registo("Cal.com", True, f"{n_slots} slots livres nos próximos 7 dias")
    else:
        registo("Cal.com", False,
                "0 slots — confirmar disponibilidade do event type no Cal.com")


def testar_railway() -> None:
    url = os.environ.get("WEBHOOK_BASE_URL", "").rstrip("/")
    if not url:
        return registo("Railway", False, "WEBHOOK_BASE_URL vazio no .env")
    try:
        r = httpx.get(f"{url}/health", timeout=15)
    except httpx.HTTPError as erro:
        return registo("Railway", False, f"não alcançável: {erro}")
    if r.status_code == 200 and r.json().get("status") == "ok":
        registo("Railway", True, f"{url}/health OK")
    else:
        registo("Railway", False, f"/health devolveu {r.status_code}: {r.text[:120]}")


def testar_gmail() -> None:
    user = os.environ.get("GMAIL_USER", "")
    pwd = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not (user and pwd):
        return registo("Gmail", False, "GMAIL_USER/GMAIL_APP_PASSWORD vazios")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(user, pwd)
        registo("Gmail", True, f"login SMTP OK como {user}")
    except (smtplib.SMTPException, OSError) as erro:
        registo("Gmail", False, f"login falhou: {erro}")


def main() -> None:
    carregar_env()
    print("A validar integrações (nada é criado/alterado)...\n")
    for teste in (testar_retell, testar_twilio, testar_calcom, testar_railway, testar_gmail):
        try:
            teste()
        except httpx.HTTPError as erro:
            registo(teste.__name__.removeprefix("testar_"), False, f"erro de rede: {erro}")
    falhas = [r for r in RESULTADOS if not r[1]]
    print(f"\n{len(RESULTADOS) - len(falhas)}/{len(RESULTADOS)} verificações OK")
    if falhas:
        print("Resolver antes de correr o setup_retell.py:")
        for nome, _, detalhe in falhas:
            print(f"  - {nome}: {detalhe}")
        sys.exit(1)
    print("Tudo pronto → uv run python scripts/setup_retell.py --buy-number")


if __name__ == "__main__":
    main()
