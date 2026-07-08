# Plano da Prova de Conceito — Recepcionista IA Fora de Horas

**Negócio:** atendimento telefónico por IA fora de horas para PMEs portuguesas de **pequenos arranjos e obras em casa** (canalização, eletricidade, montagens, pinturas, estores, fechaduras, pequenas remodelações).
**Objetivo da POC:** ter um número de telefone real que atende, faz triagem urgência/normal, aciona o técnico por SMS, marca visitas no calendário e envia relatório diário — pronto a ser demonstrado ao vivo num pitch.
**Data do plano:** 08-07-2026 · Factos técnicos verificados nas fontes indicadas em `docs/ARQUITETURA.md`.

---

## Visão geral das fases

| Fase | O quê | Quem | Duração típica |
|---|---|---|---|
| 0 | Contas e chaves | Tu | ~1h |
| 1 | Serviço de webhooks (código + testes) | Feita (neste repo) | — |
| 2 | Deploy Railway + criação do agente Retell | Tu + script | ~30 min |
| 3 | QA real (web calls + chamadas reais) | Tu | 1–2h |
| 4 | Pitch com demo ao vivo | Tu | — |
| 5 | Pós-POC: número +351, `/onboard`, piloto | Tu + Claude | dias–semanas |

A POC completa (fases 0–3) faz-se **num único dia**.

---

## Fase 0 — Contas e chaves (~1h, uma vez)

| # | Conta | Link | O que tirar de lá | Custo |
|---|---|---|---|---|
| 1 | Retell AI | https://dashboard.retellai.com | `RETELL_API_KEY` | $10 créditos grátis; número US ~$2/mês |
| 2 | Twilio (trial) | https://console.twilio.com | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, número Twilio (`TWILIO_FROM_NUMBER`) | grátis em trial |
| 3 | Cal.com (free) | https://app.cal.com | `CALCOM_API_KEY` (Settings → Security) + `CALCOM_EVENT_TYPE_ID` de um event type "Visita técnica (60 min)" | grátis |
| 4 | Railway | https://railway.com | projeto ligado ao repo GitHub | trial $5; depois Hobby $5/mês |
| 5 | Gmail | conta existente | app password (requer 2FA) para o relatório diário | grátis |

Notas importantes da Twilio trial:
- Só envia SMS para números **verificados** na consola (verifica o teu telemóvel).
- Confirmar que **Portugal** está ativo em Messaging Geographic Permissions.
- As mensagens levam o prefixo "Sent from a Twilio trial account" — aceitável na POC; a conta paga remove-o.

## Fase 1 — Serviço de webhooks ✅ (feita neste repo)

FastAPI em `webhooks/` com:
- `POST /retell/tools/notificar_tecnico` — urgências: grava e envia SMS ao dono (responde <1s, SMS em background).
- `POST /retell/tools/registar_recado` — recados para contacto na manhã seguinte.
- `POST /retell/webhook` — eventos `call_started`/`call_ended`/`call_analyzed` da Retell (resumo, sentimento, custo, transcript → SQLite).
- Relatório diário às 08:00 (Europe/Lisbon) por email + pré-visualização em `GET /relatorio/hoje?token=...`.
- Verificação da assinatura `X-Retell-Signature` em todos os endpoints.
- Testes: `uv run pytest` (15 testes).

## Fase 2 — Deploy + agente (~30 min)

Segue `docs/SETUP.md` passo a passo:
1. Deploy no Railway (deteta o `Dockerfile`; colar variáveis do `.env.example`; volume em `/data`).
2. Escolher a voz PT-PT no dashboard da Retell (candidatas: **Mariza**, **Marta**, **Joana** — ElevenLabs; usar modelo flash v2.5) e copiar o voice ID.
3. `uv run python scripts/setup_retell.py --buy-number` — cria o Retell LLM (prompt v1.1 com variables demo), o agente (pt-PT, webhook, análise pós-chamada) e compra o número US.

## Fase 3 — QA real (1–2h)

**3a. Web calls (grátis, sem telefone):** no dashboard da Retell, testar com o checklist do QA (`.claude/agents/qa.md`):
1. Abertura inclui identificação como IA + aviso de gravação — sempre.
2. "Quanto custa a urgência?" → responde "a partir de sessenta euros, o técnico confirma" — nunca preço fechado.
3. Triagem correta em 3 cenários: cano rebentado (urgência), torneira a pingar (normal), cheiro a gás (urgência + instruções de segurança + 112 se forte).
4. Recolhe nome → morada → telemóvel um de cada vez.
5. Instruções de segurança em rotura de água, gás e quadro elétrico.
6. Marcação: propõe 2 slots reais do Cal.com e cria o booking.
7. SMS de urgência chega ao telemóvel verificado.

**3b. Chamadas reais ao número US:** ⚠️ ligar de um telemóvel PT para número US paga tarifa internacional — usar poucas chamadas curtas, ou ligar via app VoIP barata. Validar: latência de resposta (<1s percebido), qualidade/sotaque da voz, interrupções.

**3c. Relatório:** confirmar `GET /relatorio/hoje?token=...` e o email das 08:00.

**Critério de saída da POC:** os 7 pontos do checklist verdes em web call + 1 chamada telefónica real completa de urgência com SMS recebido.

## Fase 4 — Pitch com demo ao vivo

Material pronto em `docs/pitch/`: guião da demo (`GUIAO-DEMO.md`), one-pager comercial e deck de slides. A demo usa o número US da POC (explicar ao prospect que o número final é português).

## Fase 5 — Pós-POC (antes do primeiro cliente pago)

1. **Número +351** — obrigatório para produção: o desvio de chamadas do cliente para um número US seria cobrado como chamada internacional. Caminho: comprar número PT na **Telnyx** (~$1/mês; exige NIF, certidão de registo comercial, comprovativo de morada <3 meses, representante) ou Twilio (regulatory bundle: identidade + morada; aprovação típica ≤3 dias úteis, pode estender-se), criar elastic SIP trunk e importar na Retell (`docs/ARQUITETURA.md`, secção telefonia). Iniciar a papelada com antecedência.
2. Testar o desvio condicional real: ativar `**61*<número do agente>#` num telemóvel PT (desativar: `##61#`).
3. Twilio pago + alphanumeric sender ID (em PT é dinâmico, sem pré-registo).
4. Automação `/onboard <url>` com os 4 subagentes (`.claude/agents/`).
5. Doc de onboarding do cliente (desvio, horários, dados do negócio).
6. Piloto com 1–2 negócios reais em trial de 14 dias.

---

## Custos

**POC (uma vez):** ~€5–10 — créditos Retell grátis ($10) cobrem as chamadas de teste; Railway trial $5; resto grátis.

**Por cliente em produção (referência jul/2026, confirmar no dashboard):**
| Componente | Custo |
|---|---|
| Retell voice engine (ElevenLabs) | $0,07/min |
| LLM (GPT-4.1) | ~$0,045/min |
| Telefonia (número próprio via SIP) | ~$0,01/min + $1–2/mês número |
| **Total por minuto** | **~$0,12–0,15/min** |
| 100–200 min/mês | **€12–28/mês por cliente** |

Com tiers de €79/€129/€179 → margem bruta >75%. (O intervalo de mercado é $0,10–0,31/min conforme voz/modelo; os valores da Retell mudam com frequência — reconfirmar antes de fechar preços.)

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Voz PT-PT soar artificial/brasileira | Mata a demo | Testar Mariza/Marta/Joana por audição em web call antes de qualquer demo; alternativa Cartesia sonic-3 |
| Latência >1s nas respostas | Conversa quebra | Modelo flash v2.5 + GPT-4.1 (sem reasoning); webhook no Railway sempre-ligado; medir `latency` nos eventos de chamada |
| Trial Twilio só envia para números verificados | SMS não chega na demo | Verificar o telemóvel do apresentador antes; produção usa conta paga |
| Demo com número US | Prospect estranha o indicativo | Dizer explicitamente "o vosso número será português"; iniciar já a papelada Telnyx |
| Preços Retell/Twilio mudam | Margem errada no pitch | Reconfirmar pricing no dashboard antes de imprimir/fechar propostas |
| Webhook lento (>10s) | Agente fica em silêncio | Já mitigado: resposta imediata + trabalho em background; healthcheck no Railway |

## Como isto sustenta o pitch

1. **Prova imediata**: o prospect liga ao número demo e é atendido em PT-PT com triagem real.
2. **Dor quantificada**: o relatório diário mostra "o que perdeu ontem" — chamadas, urgências, marcações.
3. **Fricção zero**: ativa-se com um desvio condicional (`**61*`), nada a instalar.
4. **Escala**: o onboarding automatizado (fase 5) cria um cliente novo em ~15 min — suporta o preço de setup baixo e o crescimento.
