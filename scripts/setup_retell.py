"""Cria/atualiza o agente demo na Retell AI (idempotente).

Uso:
    uv run python scripts/setup_retell.py --dry-run          # só mostra payloads
    uv run python scripts/setup_retell.py                    # cria/atualiza LLM+agente
    uv run python scripts/setup_retell.py --buy-number       # compra número US e associa

Lê RETELL_API_KEY, WEBHOOK_BASE_URL, CALCOM_API_KEY, CALCOM_EVENT_TYPE_ID e
RETELL_VOICE_ID do ambiente (ou .env na raiz). Guarda os IDs em
clients/demo/deploy.json para as execuções seguintes atualizarem em vez de criar.
"""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
PROMPT_PATH = RAIZ / "prompts" / "prompt-agente-demo-arranjos-casa.md"
VARIABLES_PATH = RAIZ / "clients" / "demo" / "variables.json"
DEPLOY_PATH = RAIZ / "clients" / "demo" / "deploy.json"
API = "https://api.retellai.com"


def carregar_env() -> None:
    """Carrega .env da raiz sem dependências externas."""
    env = RAIZ / ".env"
    if not env.exists():
        return
    for linha in env.read_text().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))


def carregar_prompt() -> tuple[str, dict]:
    prompt = PROMPT_PATH.read_text()
    variables = json.loads(VARIABLES_PATH.read_text())
    for nome, valor in variables.items():
        prompt = prompt.replace("{{" + nome + "}}", str(valor))
    por_substituir = sorted(set(re.findall(r"{{(\w+)}}", prompt)))
    if por_substituir:
        sys.exit(f"ERRO: variáveis sem valor em variables.json: {por_substituir}")
    return prompt, variables


def construir_tools(webhook_base: str, cal_api_key: str, cal_event_type_id: int) -> list:
    return [
        {
            "type": "custom",
            "name": "notificar_tecnico",
            "description": (
                "Envia SMS de alerta ao técnico de serviço com os dados da urgência. "
                "Chamar apenas em urgências, depois de recolher nome, morada e telemóvel."
            ),
            "url": f"{webhook_base}/retell/tools/notificar_tecnico",
            "speak_during_execution": True,
            "execution_message_description": (
                "Diz ao cliente que estás a enviar o alerta ao técnico neste momento."
            ),
            "speak_after_execution": True,
            "timeout_ms": 10000,
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do cliente"},
                    "morada": {
                        "type": "string",
                        "description": "Morada completa, incluindo andar se aplicável",
                    },
                    "telemovel": {
                        "type": "string",
                        "description": "Telemóvel do cliente para contacto direto",
                    },
                    "problema": {
                        "type": "string",
                        "description": "Descrição do problema e há quanto tempo começou",
                    },
                },
                "required": ["nome", "morada", "telemovel", "problema"],
            },
        },
        {
            "type": "custom",
            "name": "registar_recado",
            "description": (
                "Regista um recado para o escritório contactar o cliente na manhã "
                "seguinte. Usar em pedidos não urgentes sem marcação."
            ),
            "url": f"{webhook_base}/retell/tools/registar_recado",
            "speak_during_execution": False,
            "speak_after_execution": True,
            "timeout_ms": 10000,
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do cliente"},
                    "telemovel": {"type": "string", "description": "Telemóvel do cliente"},
                    "assunto": {
                        "type": "string",
                        "description": "Assunto do recado / serviço pretendido",
                    },
                },
                "required": ["nome", "telemovel", "assunto"],
            },
        },
        {
            "type": "check_availability_cal",
            "name": "consultar_agenda",
            "description": "Consulta os horários livres na agenda para propor ao cliente.",
            "cal_api_key": cal_api_key,
            "event_type_id": cal_event_type_id,
            "timezone": "Europe/Lisbon",
        },
        {
            "type": "book_appointment_cal",
            "name": "marcar_servico",
            "description": (
                "Marca a visita no horário escolhido, com nome e telemóvel do cliente."
            ),
            "cal_api_key": cal_api_key,
            "event_type_id": cal_event_type_id,
            "timezone": "Europe/Lisbon",
        },
        {
            "type": "end_call",
            "name": "terminar_chamada",
            "description": "Termina a chamada depois da frase de despedida.",
        },
    ]


def payload_llm(prompt: str, variables: dict, tools: list) -> dict:
    abertura = (
        f"{variables['nome_empresa']}, boa noite. Sou a {variables['nome_agente']}, "
        "a assistente virtual da empresa. Esta chamada é atendida por inteligência "
        "artificial e pode ser gravada para garantir o seu atendimento. "
        "Em que posso ajudar?"
    )
    return {
        "model": "gpt-4.1",
        "general_prompt": prompt,
        "general_tools": tools,
        "begin_message": abertura,
        "start_speaker": "agent",
    }


def payload_agente(llm_id: str, webhook_base: str) -> dict:
    voice_id = os.environ.get("RETELL_VOICE_ID", "11labs-Adrian")
    payload = {
        "agent_name": "Demo Arranjos Horizonte (PT-PT)",
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
        "voice_id": voice_id,
        # cada fornecedor TTS tem os seus voice_models — ajustar se a voz não for ElevenLabs
        "voice_model": os.environ.get("RETELL_VOICE_MODEL", "eleven_flash_v2_5"),
        "language": "pt-PT",
        # sem isto a rede telefónica engole o início da abertura de compliance
        "begin_message_delay_ms": 1200,
        "stt_mode": "accurate",
        # ruído/monossílabos não devem cortar a abertura a meio (default é 1)
        "interruption_sensitivity": 0.6,
        "webhook_url": f"{webhook_base}/retell/webhook",
        "post_call_analysis_data": [
            {
                "type": "enum",
                "name": "tipo_pedido",
                "description": "Classificação do motivo da chamada.",
                "choices": ["urgencia", "marcacao", "recado", "outro"],
            },
            {
                "type": "string",
                "name": "nome_cliente",
                "description": "Nome do cliente, se tiver sido recolhido.",
                "examples": ["Maria Silva"],
            },
        ],
    }
    fallbacks = os.environ.get("RETELL_FALLBACK_VOICE_IDS", "")
    if fallbacks:
        payload["fallback_voice_ids"] = [v.strip() for v in fallbacks.split(",") if v.strip()]
    return payload


def pedir(client: httpx.Client, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    resposta = client.request(metodo, f"{API}{caminho}", json=corpo)
    if resposta.status_code >= 300:
        sys.exit(f"ERRO Retell {metodo} {caminho}: {resposta.status_code} {resposta.text}")
    return resposta.json() if resposta.text else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="mostra payloads sem chamar a API")
    parser.add_argument("--buy-number", action="store_true", help="compra número US e associa o agente")
    args = parser.parse_args()

    carregar_env()
    api_key = os.environ.get("RETELL_API_KEY", "")
    webhook_base = os.environ.get("WEBHOOK_BASE_URL", "").rstrip("/")
    cal_api_key = os.environ.get("CALCOM_API_KEY", "")
    cal_event_type_id = int(os.environ.get("CALCOM_EVENT_TYPE_ID") or "0")

    faltam = [
        nome
        for nome, valor in {
            "RETELL_API_KEY": api_key,
            "WEBHOOK_BASE_URL": webhook_base,
            "CALCOM_API_KEY": cal_api_key,
            "CALCOM_EVENT_TYPE_ID": cal_event_type_id,
        }.items()
        if not valor
    ]
    if faltam and not args.dry_run:
        sys.exit(f"ERRO: variáveis em falta no ambiente/.env: {faltam}")

    prompt, variables = carregar_prompt()
    tools = construir_tools(webhook_base or "https://EXEMPLO.up.railway.app",
                            cal_api_key or "cal_live_EXEMPLO",
                            cal_event_type_id or 0)
    llm = payload_llm(prompt, variables, tools)

    if args.dry_run:
        # não imprimir a API key real do Cal.com
        seguro = json.loads(json.dumps(llm))
        for tool in seguro["general_tools"]:
            if "cal_api_key" in tool:
                tool["cal_api_key"] = "cal_live_<REDIGIDA>"
        print("--- payload create/update-retell-llm ---")
        print(json.dumps(seguro, ensure_ascii=False, indent=2))
        print("--- payload create/update-agent (llm_id=<pendente>) ---")
        print(json.dumps(payload_agente("<llm_id>", webhook_base or "https://EXEMPLO.up.railway.app"),
                         ensure_ascii=False, indent=2))
        return

    estado = json.loads(DEPLOY_PATH.read_text()) if DEPLOY_PATH.exists() else {}
    with httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=30) as client:
        if estado.get("llm_id"):
            pedir(client, "PATCH", f"/update-retell-llm/{estado['llm_id']}", llm)
            llm_id = estado["llm_id"]
            print(f"Retell LLM atualizado: {llm_id}")
        else:
            llm_id = pedir(client, "POST", "/create-retell-llm", llm)["llm_id"]
            print(f"Retell LLM criado: {llm_id}")

        agente = payload_agente(llm_id, webhook_base)
        if estado.get("agent_id"):
            pedir(client, "PATCH", f"/update-agent/{estado['agent_id']}", agente)
            agent_id = estado["agent_id"]
            print(f"Agente atualizado: {agent_id}")
        else:
            agent_id = pedir(client, "POST", "/create-agent", agente)["agent_id"]
            print(f"Agente criado: {agent_id}")

        numero = estado.get("phone_number")
        if args.buy_number and not numero:
            resposta = pedir(client, "POST", "/create-phone-number",
                             {"inbound_agents": [{"agent_id": agent_id, "weight": 1}],
                              "nickname": "demo-arranjos"})
            numero = resposta.get("phone_number")
            print(f"Número comprado e associado: {numero}")
        elif args.buy_number:
            print(f"Número já existente: {numero} (nada a comprar)")

    DEPLOY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEPLOY_PATH.write_text(json.dumps({
        "llm_id": llm_id,
        "agent_id": agent_id,
        "phone_number": numero,
        "webhook_base_url": webhook_base,
        "atualizado_em": datetime.now(UTC).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"Estado guardado em {DEPLOY_PATH.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
