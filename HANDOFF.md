# Handoff de sessão — voice-onboard
Data: 2026-07-08 (atualizado na sessão de implementação da POC)
Pasta de trabalho: raiz deste repo
Branch / git: `claude/context-overview-fiv9e5` (repo GitHub `Joak81/voiceAssistant`; é o branch default por o repo ter nascido vazio)

## 1. Objetivo
Montar o negócio de atendimento telefónico por IA fora de horas ("AI receptionist") para PMEs portuguesas, começando pelo nicho **pequenos arranjos e obras em casa** (decisão de 08-07: alargado de canalizadores/eletricistas para handyman/multiserviços — canalização, eletricidade, montagens, pinturas, estores, fechaduras, pequenas remodelações). Dois entregáveis: infraestrutura por cliente na Retell AI, e agente de onboarding em Claude Code que cria cada novo cliente em ~15 minutos.

## 2. Estado atual
**Fases 0–2 da POC concluídas** (09-07-2026): o sistema está VIVO em produção.
- Railway: `https://voiceassistant-production-4750.up.railway.app` (projeto voice-onboard, volume /data, variáveis todas definidas; /health OK).
- Agente Retell: `agent_27aace7dfe1c09958ca3627b54` (LLM `llm_a28bdf870e2e5fad80c867b33b64`), 5 tools, pt-PT.
- **Voz PT-PT ativa**: "Marta – Warm Confident" (ElevenLabs `bBNhdwrIjl4fcVYiRbT2` → Retell `custom_voice_1ab1171f938943441b9e3c591a`, flash v2.5). Alternativas já adicionadas à conta, troca por PATCH do agente: Joana `custom_voice_df7c523638bfb6d55c89304cac`, Maria `custom_voice_63b69136a882b44168c0286085`. Só existe 1 voz nativa "portuguesa" na Retell e é PT-BR — usar sempre community voices PT-PT da ElevenLabs.
- **Número demo: +1 (270) 716-4091** — associado ao agente, pronto a atender.
- Twilio: número +1 208 974 8700 a enviar SMS (teste real recebido no telemóvel do dono, +351 919 000 957, verificado).
- Cal.com validado (event type 6253265, 48 slots). Gmail configurado (envio testa-se no relatório das 08:00).
- **Dashboard do dono**: `GET /dashboard?token=<REPORT_TOKEN>` no serviço Railway — KPIs, urgências (estado do SMS), marcações reais do Cal.com, recados e chamadas com transcript. SMS corrigido para formato compacto ASCII (erro 30044 da trial: limite de segmentos) — entrega confirmada DELIVERED.
- **Motor Grok (custom LLM)**: `webhooks/grok_llm.py` implementa o protocolo Custom LLM da Retell em `wss://<railway>/llm-websocket/{call_id}` com Grok (xAI, `grok-4.1-fast`, OpenAI-compatível) e os 5 tools executados in-process (agenda via Cal.com API, urgências/recados via storage+notify). Trocar de motor: `scripts/mudar_motor.py grok|retell` (rollback a um comando; o retell-llm GPT-4.1 continua criado). Requer `XAI_API_KEY` no Railway/.env. O pós-chamada (call_analyzed→dashboard/relatório) não muda.
- Falta: **Fase 3 (QA humano)** — web calls com o checklist, audição/escolha da voz PT-PT (Mariza/Marta/Joana), chamada real; e Fase 5 (pós-POC).
- Segredos: só no .env local da sessão e nas variáveis do Railway; nunca em git. `docs/mapa-contas.html` explica contas e fluxos.

## 3. Já feito
- **Pesquisa técnica verificada (jul/2026)** com fontes: APIs Retell (tools, webhooks, assinatura), telefonia PT (+351 só via SIP trunk importado; desviar para número US = tarifa internacional → produção exige +351), vozes PT-PT (usar `eleven_flash_v2_5`; candidatas Mariza/Marta/Joana), Cal.com v2, Twilio trial, Railway.
- **`webhooks/`** — FastAPI: `notificar_tecnico` (SMS Twilio em background), `registar_recado`, `/retell/webhook` (call_started/ended/analyzed → SQLite), relatório diário 08:00 Europe/Lisbon por email, verificação `X-Retell-Signature` (esquema exato do SDK oficial), `/health`, `/relatorio/hoje?token=`. Testes em `tests/`.
- **`scripts/setup_retell.py`** — idempotente: Retell LLM (gpt-4.1, prompt v1.1, begin_message com abertura compliance) + agente (pt-PT, flash v2.5, webhook, post_call_analysis_data com `tipo_pedido`) + tools: 2 custom (webhook), 2 nativos Cal.com (`consultar_agenda`/`marcar_servico`), end_call; `--buy-number`, `--dry-run`; estado em `clients/demo/deploy.json`.
- **`prompts/prompt-agente-demo-arranjos-casa.md`** — template base v1.1, nicho alargado, urgências acrescidas (quadro elétrico, fechadura), sem tool de resumo in-call (o resumo vem do `call_analyzed`). O de canalizadores ficou como variante setorial.
- **`docs/`** — `PLANO-POC.md` (fases 0–5, custos, riscos, critérios de saída), `ARQUITETURA.md` (Mermaid: componentes, urgência, marcação, pós-chamada, telefonia +351, pipeline onboarding), `SETUP.md` (operacional), `pitch/GUIAO-DEMO.md` + one-pager + deck HTML.
- Deploy: `Dockerfile` + `railway.json` (healthcheck; o modo serverless/sleep desliga-se no dashboard — ver SETUP §2.5). `.env.example` completo.
- Decisões anteriores mantidas: pricing €79/129/179 + setup €200–400; GTM demo ao vivo; compliance inviolável.

## 4. Por fazer (próximos passos)
1. **Fase 0 do PLANO-POC** (dono): criar contas Retell/Twilio/Cal.com/Railway/Gmail app password — checklist em `docs/PLANO-POC.md`.
2. **Fase 2**: deploy Railway (variables + volume `/data` + domínio) e `uv run python scripts/setup_retell.py --buy-number`. Guia: `docs/SETUP.md`.
3. **Fase 3**: QA real — web calls com o checklist de 7 pontos, escolha da voz por audição, 1 chamada real, relatório.
4. **Fase 5 (pós-POC)**: iniciar papelada do número +351 (Telnyx ~$1/mês: NIF+certidão+morada; ou Twilio bundle), testar desvio `**61*`, automação `/onboard`, doc de onboarding do cliente, piloto 14 dias.

## 5. Decisões e raciocínio (novas nesta sessão)
- **Nicho alargado** a pequenos arranjos e obras em casa (mercado maior; urgências de canalização/eletricidade mantêm-se como gancho de vendas).
- **Railway** em vez de Mac Mini + túnel (sempre-ligado, URL estável, $5/mês; Render free adormece → rejeitado; manter serverless OFF).
- **Tools nativos Cal.com da Retell** para agenda em vez de custom functions próprias (menos código e falhas).
- **`resumo_chamada` eliminado como tool**: o evento `call_analyzed` já traz `call_summary` + `custom_analysis_data` (definimos `tipo_pedido` enum: urgencia/marcacao/recado/outro).
- **Voz**: `eleven_flash_v2_5` (multilingual v2 é lento demais para telefonia); LLM `gpt-4.1` (recomendação Retell; evitar reasoning models).
- **Custos reais por minuto** ~$0,12–0,15 (voz $0,07 + LLM ~$0,045 + telefonia); intervalo de mercado $0,10–0,31 — margens do pricing confirmadas.
- **POC com número US** (decisão do dono): valida tudo exceto o desvio nacional; +351 é bloqueador só para produção.

## 6. Ficheiros relevantes
- `docs/PLANO-POC.md` — plano mestre da POC (fases, custos, riscos, critérios de saída).
- `docs/ARQUITETURA.md` — arquitetura e fluxos (Mermaid).
- `docs/SETUP.md` — passo-a-passo operacional (contas → deploy → agente → testes).
- `docs/pitch/` — guião da demo, one-pager e deck (HTML autónomos).
- `webhooks/` + `tests/` — serviço e testes (`uv run pytest`).
- `scripts/setup_retell.py` — deploy do agente demo.
- `prompts/prompt-agente-demo-arranjos-casa.md` — template base v1.1.

## 7. Comandos úteis
- `uv sync && uv run pytest` — instalar e testar.
- `VERIFY_SIGNATURE=false uv run uvicorn webhooks.main:app --reload --port 8000` — dev local.
- `uv run python scripts/setup_retell.py --dry-run` — inspecionar payloads Retell.
- Docs Retell: https://docs.retellai.com · Cal.com API: https://cal.com/docs/api-reference/v2

## 8. Problemas em aberto / armadilhas
- **Voz PT-PT por validar com audição real** — nenhuma voz foi ouvida; escolher entre Mariza/Marta/Joana em web call antes de qualquer demo.
- Twilio trial: SMS só para números verificados (~5), ~50/dia, com prefixo de trial. Produção → conta paga + alphanumeric sender (dinâmico em PT).
- Números +351: papelada Telnyx/Twilio demora dias a semanas — iniciar cedo se houver piloto à vista.
- Preços Retell mudam com frequência (telefonia já subiu de $0,01 para $0,015/min em 2026) — reconfirmar antes de fechar pricing.
- Webhook: responder <1s (já implementado assim); a Retell corta a 10s nos eventos e faz retry.
- O repo nasceu vazio → o branch `claude/context-overview-fiv9e5` é o default; se se quiser `main`, criar a partir deste.

## 9. Contexto a preservar (snippets / valores)
- Custos por componente (jul/2026): voice engine $0,07/min (ElevenLabs) · LLM $0,003–0,08/min (gpt-4.1 ≈ $0,045) · telefonia Retell $0,015/min (própria via SIP ≈ $0,01) · número $2/mês (Telnyx PT ~$1).
- Desvio condicional (qualquer operador PT): ativar `**61*<número>#` · desativar `##61#` · verificar `*#61#` · cancelar tudo `##002#`. A perna desviada é paga por quem desvia, ao preço do tarifário (nacional se o destino for +351).
- Assinatura Retell: header `X-Retell-Signature` = `v=<ts_ms>,d=<hmac_sha256_hex(api_key, corpo+ts)>`, janela 5 min.
- Gancho de abertura do pitch: "Ontem às 21h40 liguei para a vossa empresa e ninguém atendeu. Eu não era cliente a sério — mas se fosse, hoje o serviço era do vosso concorrente."
- Objeções: máquinas → "preferem uma máquina que resolve a um voicemail que ninguém ouve"; caro → "uma urgência recuperada paga dois meses". Fecho: "Levo 15 minutos a pôr isto a funcionar. Quer que fique ativo já esta noite?"

## 10. Como retomar
Cola isto numa sessão nova do Claude Code na raiz do projeto:
"Lê o HANDOFF.md e o CLAUDE.md. Não recomeces o que está em 'Já feito'. Confirma comigo o passo 1 de 'Por fazer' e avança."
