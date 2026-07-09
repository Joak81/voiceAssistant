# SETUP — do zero ao número a atender (~1h30)

Passo a passo operacional da POC. Pré-requisito: este repo clonado e `uv` instalado (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

## 1. Contas (Fase 0 do PLANO-POC)

### 1.1 Retell AI
1. Conta em https://dashboard.retellai.com (traz $10 de créditos).
2. Dashboard → API Keys → criar e guardar `RETELL_API_KEY`.

### 1.2 Twilio (trial)
1. Conta em https://console.twilio.com.
2. Guardar `TWILIO_ACCOUNT_SID` e `TWILIO_AUTH_TOKEN` (página inicial da consola).
3. Obter um número trial (Phone Numbers → Buy/Get trial number) → `TWILIO_FROM_NUMBER`.
4. **Verificar o teu telemóvel** (Verified Caller IDs) — em trial só recebe SMS quem está verificado.
5. Messaging → Geographic Permissions → confirmar **Portugal** ativo.

### 1.3 Cal.com (free)
1. Conta em https://app.cal.com; definir disponibilidade de trabalho.
2. Criar event type "Visita técnica" (60 min). O ID numérico está no URL do event type → `CALCOM_EVENT_TYPE_ID`.
3. Settings → Security → API key → `CALCOM_API_KEY` (prefixo `cal_live_`).

### 1.4 Gmail (relatório diário)
1. Ativar 2FA na conta Google.
2. https://myaccount.google.com/apppasswords → criar app password → `GMAIL_APP_PASSWORD` (+ `GMAIL_USER` = o teu email).

### 1.5 Railway
1. Conta em https://railway.com (login com GitHub).

## 2. Deploy no Railway (~15 min)

1. New Project → Deploy from GitHub repo → escolher este repo. O Railway usa o `Dockerfile` automaticamente (`railway.json` já define healthcheck `/health`).
2. No serviço → **Variables** → colar as variáveis do `.env.example` com os valores reais. Definir `DB_PATH=/data/voice.db`.
3. No serviço → **Volumes** → adicionar volume montado em `/data` (persistência do SQLite entre deploys).
4. Settings → Networking → **Generate Domain** → guardar o URL (ex.: `https://xxxx.up.railway.app`) → é o `WEBHOOK_BASE_URL`.
5. ⚠️ Confirmar que o modo **serverless/sleep está desligado** (Settings → Deploy) — cold starts quebram o requisito de resposta <1–2s.
6. Testar: `curl https://xxxx.up.railway.app/health` → `{"status":"ok"}`.

## 3. Voz PT-PT (~10 min)

1. Dashboard Retell → qualquer agente → campo Voice → **Add custom voice** → pesquisar na voice library da ElevenLabs por vozes femininas de português europeu — candidatas: **Mariza**, **Marta (Warm Confident)**, **Joana**.
2. Ouvir as pré-visualizações; escolher uma e copiar o **voice ID** → `RETELL_VOICE_ID`.
3. O script usa `voice_model: eleven_flash_v2_5` (baixa latência, suporta PT). Evitar multilingual v2 (lento para tempo real) e vozes PT-BR.

## 4. Criar o agente (~5 min)

Na raiz do repo, com o `.env` preenchido (copiar de `.env.example`):

```bash
uv run python scripts/setup_retell.py --dry-run    # inspecionar payloads
uv run python scripts/setup_retell.py --buy-number # criar LLM + agente + número US
```

O script é idempotente: guarda `clients/demo/deploy.json` e nas execuções seguintes atualiza em vez de criar. Depois de qualquer edição ao prompt ou às tools, basta voltar a correr.

## 5. Testar (Fase 3 do PLANO-POC)

1. **Web call** (grátis): dashboard Retell → agente → Test. Percorrer o checklist QA de `docs/PLANO-POC.md` (abertura compliance, triagem, preço "a partir de", marcação, recado).
2. **SMS**: simular urgência na web call → SMS deve chegar ao telemóvel verificado.
3. **Chamada real**: ligar ao número US comprado (tarifa internacional — chamadas curtas).
4. **Relatório**: `curl "https://xxxx.up.railway.app/relatorio/hoje?token=<REPORT_TOKEN>"`; o email chega às 08:00 Lisboa.
5. **Dashboard**: abrir `https://xxxx.up.railway.app/dashboard?token=<REPORT_TOKEN>` no browser — chamadas, urgências (com estado do SMS), marcações do Cal.com e recados, com auto-refresh. Guardar nos favoritos.

## 6. Desenvolvimento local

```bash
uv sync                                   # instalar dependências
uv run pytest                             # 15 testes
VERIFY_SIGNATURE=false uv run uvicorn webhooks.main:app --reload --port 8000
```

Com `VERIFY_SIGNATURE=false` podes fazer curl sem assinar os pedidos. Para testar com assinatura, gera-a com `webhooks.security.assinar(corpo, api_key)`.

## Resolução de problemas

| Sintoma | Causa provável | Correção |
|---|---|---|
| 401 em todos os webhooks | `RETELL_API_KEY` no Railway ≠ key da conta que chama | Usar a mesma key nos dois lados |
| Agente fica em silêncio ao acionar técnico | Webhook lento/inacessível | `curl /health`; ver logs no Railway; confirmar `WEBHOOK_BASE_URL` correto nas tools (re-correr o script) |
| SMS não chega | Número não verificado na trial / geo-permissions | Verificar o número na consola Twilio; ativar Portugal |
| Voz soa brasileira | Voz errada ou language mal definido | Escolher voz PT-PT da lista; `language` é `pt-PT` (já no script) |
| Marcação falha | `CALCOM_EVENT_TYPE_ID` errado ou sem disponibilidade | Confirmar ID do event type e disponibilidade no Cal.com |
| Email do relatório não chega | App password/2FA | Recriar app password; ver logs às 08:00 |
