# Arquitetura Técnica — Recepcionista IA Fora de Horas

Versão: POC (jul/2026). Fontes técnicas verificadas: docs.retellai.com (custom functions, webhooks, custom telephony), SDKs oficiais Retell (Python/TypeScript), cal.com/docs (API v2), Twilio/Telnyx (números PT).

## 1. Componentes do sistema

```mermaid
flowchart LR
    subgraph Cliente["Cliente final"]
        C[Telefone do cliente]
    end

    subgraph Negocio["Negócio (PME)"]
        N[Número da empresa]
        D[Telemóvel do dono]
        E[Email do dono]
    end

    subgraph Retell["Retell AI (voz)"]
        NUM[Número do agente]
        AG[Agente de voz<br/>prompt PT-PT v1.1]
        LLM[LLM GPT-4.1]
        TTS[Voz ElevenLabs<br/>flash v2.5 pt-PT]
        AN[Análise pós-chamada]
    end

    subgraph Railway["Railway (FastAPI — este repo)"]
        WH[/retell/tools/*<br/>notificar_tecnico · registar_recado/]
        EV[/retell/webhook<br/>call_started · ended · analyzed/]
        DB[(SQLite<br/>chamadas · urgências · recados)]
        REP[Relatório diário 08:00]
    end

    CAL[Cal.com<br/>agenda + bookings]
    TW[Twilio SMS]

    C -->|liga fora de horas| N -->|desvio condicional **61*| NUM
    NUM --> AG
    AG <--> LLM
    AG <--> TTS
    AG -->|tools nativos<br/>consultar_agenda · marcar_servico| CAL
    AG -->|custom functions HTTP<br/>assinadas| WH
    AG --> AN -->|call_analyzed| EV
    WH --> DB
    EV --> DB
    WH -->|SMS urgência| TW --> D
    DB --> REP -->|email 08:00| E
```

**Decisões-chave**
- **Agenda pelos tools nativos Cal.com da Retell** (`check_availability_cal`/`book_appointment_cal`, com os nomes `consultar_agenda`/`marcar_servico`): zero código nosso no caminho da marcação.
- **Resumo de chamada pelo evento `call_analyzed`** (a plataforma produz `call_summary`, sentimento e `custom_analysis_data.tipo_pedido`): não existe tool in-call de resumo.
- **Webhook responde <1s** — a Retell corta custom functions lentas e o cliente fica em silêncio; SMS e escritas seguem em background.
- **Segurança**: todos os endpoints verificam `X-Retell-Signature` (HMAC-SHA256 da API key sobre corpo+timestamp, janela de 5 min — mesmo esquema do SDK oficial).

## 2. Fluxo de chamada — URGÊNCIA

```mermaid
sequenceDiagram
    autonumber
    participant C as Cliente
    participant A as Agente Retell (Marta)
    participant W as FastAPI (Railway)
    participant T as Twilio
    participant D as Dono do negócio

    C->>A: Liga (fora de horas, via desvio)
    A->>C: Abertura compliance: "…sou assistente virtual…<br/>chamada atendida por IA e pode ser gravada…"
    C->>A: "Rebentou um cano na cozinha!"
    A->>C: Triagem → URGÊNCIA. Recolhe nome, morada, telemóvel (um a um)
    A->>C: Instruções de segurança (fechar torneira geral / gás → 112)
    A->>W: POST /retell/tools/notificar_tecnico {nome, morada, telemovel, problema}
    W->>W: Grava urgência (SQLite) e responde já
    W-->>A: 200 {"resultado": "alerta enviado…"} (<1s)
    W--)T: SMS em background
    T--)D: "URGENCIA: Maria Silva, Rua X…, cano rebentado. Ligar em 15-30min"
    A->>C: "Já enviei o alerta. Vai ser contactado em 15 a 30 minutos."
    A->>C: Nunca promete hora exata nem preço fechado ("a partir de 60€…")
    Note over A: Fim da chamada → análise pós-chamada (secção 4)
```

## 3. Fluxo de chamada — PEDIDO NORMAL (marcação)

```mermaid
sequenceDiagram
    autonumber
    participant C as Cliente
    participant A as Agente Retell
    participant CAL as Cal.com

    C->>A: "Queria alguém para montar uns móveis"
    A->>C: Triagem → NORMAL. Percebe o serviço em 1-2 perguntas
    A->>CAL: consultar_agenda (tool nativo → GET /v2/slots)
    CAL-->>A: Slots livres
    A->>C: "Tenho amanhã às dez ou quinta às três. Qual prefere?"
    C->>A: "Quinta às três."
    A->>C: Recolhe nome, morada, telemóvel
    A->>CAL: marcar_servico (tool nativo → POST /v2/bookings)
    CAL-->>A: Booking criado (email/SMS de confirmação do Cal.com)
    A->>C: Confirma em voz alta dia, hora e morada
    Note over A,CAL: Sem vaga, preferência do cliente ou orçamento de obra →<br/>registar_recado no webhook (contacto na manhã seguinte)
```

## 4. Pós-chamada e relatório diário

```mermaid
sequenceDiagram
    autonumber
    participant R as Retell
    participant W as FastAPI (Railway)
    participant DB as SQLite
    participant G as Gmail SMTP
    participant D as Dono

    R->>W: POST /retell/webhook {event: call_started, call}
    R->>W: POST /retell/webhook {event: call_ended, call}
    R->>W: POST /retell/webhook {event: call_analyzed, call}
    Note right of R: call_analysis: call_summary, user_sentiment,<br/>custom_analysis_data.tipo_pedido, call_cost
    W->>DB: upsert da chamada (resumo, tipo, custo, transcript)
    Note over W: Todos os dias às 08:00 Europe/Lisbon (APScheduler)
    W->>DB: Agrega últimas 24h
    W->>G: Email: chamadas, urgências, marcações, recados, custo
    G->>D: "Relatório diário — 3 chamadas, 1 urgência, 1 marcação…"
```

## 5. Telefonia em produção (+351)

A Retell só vende números US/CA. Em produção o agente precisa de um **número português importado**, porque o desvio do número da empresa para um número US seria cobrado ao dono como chamada internacional; para um +351 conta como chamada nacional (normalmente incluída no tarifário).

```mermaid
flowchart LR
    subgraph PT["Operador PT do cliente (MEO/NOS/Vodafone)"]
        NC[Número da empresa]
    end
    subgraph Carrier["Telnyx ou Twilio"]
        NPT["Número +351<br/>(~$1-2/mês)"]
        SIP[Elastic SIP Trunk]
    end
    subgraph Retell["Retell AI"]
        IMP[Número importado<br/>import-phone-number]
        AG[Agente]
    end

    NC -->|"desvio condicional **61*numero#<br/>(chamada nacional)"| NPT
    NPT --> SIP -->|"Origination URI: sip:sip.retellai.com<br/>auth: credenciais ou IP allowlist 18.98.16.120/30"| IMP --> AG
```

**Passos (Twilio como exemplo):** comprar número PT (regulatory bundle: identidade + comprovativo de morada <3 meses, sem apartado; aprovação típica ≤3 dias úteis, pode demorar mais) → criar Elastic SIP Trunk → Origination URI `sip:sip.retellai.com` → importar na Retell em E.164 com o termination URI + credenciais → associar o agente. Na Telnyx o processo é análogo (requisitos PT: NIF, certidão de registo comercial, morada compatível com o indicativo).

**Desvio no telemóvel/fixo do cliente (qualquer operador PT):**
- Ativar (se não atender): `**61*<número do agente>#`
- Desativar: `##61#` · Verificar: `*#61#`

## 6. Pipeline de onboarding de novos clientes (`/onboard <url>`)

```mermaid
flowchart LR
    U["/onboard https://sitedocliente.pt"] --> S

    subgraph Subagentes[".claude/agents/"]
        S["scraper<br/>site + Google Maps → JSON<br/>(serviços, preços, horário, zonas, FAQ)"]
        P["prompt-builder<br/>template base + JSON → prompt.md<br/>+ variables.json (compliance intocável)"]
        DEP["deployer<br/>API Retell: LLM + agente + número<br/>+ tools → deploy.json"]
        Q["qa<br/>chamadas de teste, checklist 7 pontos<br/>só aprova com tudo verde"]
    end

    S --> P --> DEP --> Q
    Q -->|falhas| P
    Q -->|aprovado| OK["Cliente ativo (~15 min)"]
```

O contrato entre subagentes está descrito em cada ficheiro de `.claude/agents/`. O `scripts/setup_retell.py` é a materialização do deployer para o cliente demo — o deployer generaliza-o por cliente (`clients/<nome>/`).

## 7. Estrutura do repositório

```
prompts/                     templates de system prompt
  prompt-agente-demo-arranjos-casa.md   ← template base v1.1 (nicho alargado)
  prompt-agente-demo-canalizadores.md   ← variante setorial v1.0
clients/demo/                variables.json + deploy.json do agente demo
webhooks/                    FastAPI (tools, eventos, relatório, SQLite)
scripts/setup_retell.py      cria/atualiza o agente na Retell (idempotente)
tests/                       pytest (15 testes)
docs/                        este ficheiro, PLANO-POC, SETUP, pitch/
.claude/agents/              subagentes do onboarding
Dockerfile + railway.json    deploy no Railway
```
