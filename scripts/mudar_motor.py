"""Troca o motor do número demo: Grok (custom LLM) ↔ Retell LLM (GPT-4.1).

A Retell não permite mudar o response_engine de um agente com versões, por
isso existem DOIS agentes (o original retell-llm e um gémeo custom-llm/Grok)
e o que se troca é o agente inbound do número. O gémeo é criado na primeira
utilização, herdando voz/língua/webhook/análise do agente original, e fica
registado em clients/demo/deploy.json (grok_agent_id).

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
DEPLOY_PATH = RAIZ / "clients" / "demo" / "deploy.json"
API = "https://api.retellai.com"


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


def pedir(client: httpx.Client, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    r = client.request(metodo, f"{API}{caminho}", json=corpo)
    if r.status_code >= 300:
        sys.exit(f"ERRO Retell {metodo} {caminho}: {r.status_code} {r.text[:300]}")
    return r.json() if r.text else {}


def garantir_agente_grok(client: httpx.Client, deploy: dict) -> str:
    """Cria o agente gémeo custom-llm se ainda não existir; devolve o id."""
    if deploy.get("grok_agent_id"):
        return deploy["grok_agent_id"]
    base = (os.environ.get("WEBHOOK_BASE_URL") or deploy.get("webhook_base_url")
            or sys.exit("falta WEBHOOK_BASE_URL"))
    ws_url = base.replace("https://", "wss://").rstrip("/") + "/llm-websocket"
    original = pedir(client, "GET", f"/get-agent/{deploy['agent_id']}")
    novo = {
        "agent_name": (original.get("agent_name") or "Demo") + " · Grok",
        "response_engine": {"type": "custom-llm", "llm_websocket_url": ws_url},
        "voice_id": original["voice_id"],
        "language": original.get("language", "pt-PT"),
        "webhook_url": original.get("webhook_url"),
    }
    for campo in ("voice_model", "fallback_voice_ids", "post_call_analysis_data",
                  "voice_speed", "voice_temperature"):
        if original.get(campo) is not None:
            novo[campo] = original[campo]
    criado = pedir(client, "POST", "/create-agent", novo)
    deploy["grok_agent_id"] = criado["agent_id"]
    print(f"Agente Grok criado: {criado['agent_id']} (voz {novo['voice_id']})")
    return criado["agent_id"]


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("grok", "retell"):
        sys.exit(__doc__)
    motor = sys.argv[1]
    carregar_env()
    api_key = os.environ.get("RETELL_API_KEY") or sys.exit("falta RETELL_API_KEY")
    deploy = json.loads(DEPLOY_PATH.read_text())
    numero = deploy.get("phone_number") or sys.exit("sem phone_number em deploy.json")

    with httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=30) as client:
        agent_id = (garantir_agente_grok(client, deploy) if motor == "grok"
                    else deploy["agent_id"])
        pedir(client, "PATCH", f"/update-phone-number/{numero}",
              {"inbound_agents": [{"agent_id": agent_id, "weight": 1}]})

    deploy["motor_ativo"] = motor
    DEPLOY_PATH.write_text(json.dumps(deploy, ensure_ascii=False, indent=2) + "\n")
    print(f"Número {numero} agora atendido pelo motor: {motor} (agente {agent_id})")


if __name__ == "__main__":
    main()
