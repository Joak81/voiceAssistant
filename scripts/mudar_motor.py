"""Troca o motor do agente demo: Grok (custom LLM) ↔ Retell LLM (GPT-4.1).

Uso:
    uv run python scripts/mudar_motor.py grok
    uv run python scripts/mudar_motor.py retell
"""

import json
import os
import sys
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
DEPLOY = json.loads((RAIZ / "clients" / "demo" / "deploy.json").read_text())


def carregar_env() -> None:
    env = RAIZ / ".env"
    if not env.exists():
        return
    for linha in env.read_text().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("grok", "retell"):
        sys.exit(__doc__)
    motor = sys.argv[1]
    carregar_env()
    api_key = os.environ.get("RETELL_API_KEY") or sys.exit("falta RETELL_API_KEY")

    if motor == "grok":
        base = (os.environ.get("WEBHOOK_BASE_URL")
                or DEPLOY.get("webhook_base_url")
                or sys.exit("falta WEBHOOK_BASE_URL"))
        ws_url = base.replace("https://", "wss://").rstrip("/") + "/llm-websocket"
        engine = {"type": "custom-llm", "llm_websocket_url": ws_url}
    else:
        engine = {"type": "retell-llm", "llm_id": DEPLOY["llm_id"]}

    r = httpx.patch(
        f"https://api.retellai.com/update-agent/{DEPLOY['agent_id']}",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"response_engine": engine},
        timeout=30,
    )
    if r.status_code >= 300:
        sys.exit(f"ERRO: {r.status_code} {r.text[:300]}")
    print(f"Agente {DEPLOY['agent_id']} agora com motor: {motor}")
    print(f"response_engine: {json.dumps(r.json().get('response_engine'), ensure_ascii=False)}")


if __name__ == "__main__":
    main()
