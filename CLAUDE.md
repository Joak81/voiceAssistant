# voice-onboard

Negócio de atendimento telefónico por IA fora de horas (AI receptionist) para PMEs portuguesas. Nicho inicial: **pequenos arranjos e obras em casa** (canalização, eletricidade, montagens, pinturas, estores, fechaduras, pequenas remodelações). Este repo contém (a) os assets por cliente na Retell AI, (b) o serviço de webhooks e (c) o agente de onboarding que automatiza a criação de cada novo cliente.

## Arquitetura

- **Plataforma de voz:** Retell AI (agente, voz ElevenLabs `eleven_flash_v2_5` pt-PT, número, telefonia). Docs: https://docs.retellai.com
- **Webhooks (este repo):** FastAPI em `webhooks/` no **Railway** (sempre-ligado; modo serverless desligado) — custom functions `notificar_tecnico` e `registar_recado` + eventos de chamada (`call_analyzed` traz o resumo; não há tool in-call de resumo).
- **Marcações:** tools **nativos** Cal.com da Retell (`check_availability_cal`/`book_appointment_cal`, nomeados `consultar_agenda`/`marcar_servico`) — sem código nosso.
- **Notificações:** Twilio SMS para o dono (urgências) + relatório diário às 8h por email (APScheduler + Gmail SMTP).
- **Onboarding:** comando `/onboard <url>` → subagentes em `.claude/agents/` (scraper → prompt-builder → deployer → qa). O `scripts/setup_retell.py` é o deploy do cliente demo.
- Desenho completo e fluxos: `docs/ARQUITETURA.md`. Plano e testes da POC: `docs/PLANO-POC.md`. Operação: `docs/SETUP.md`.

## Estrutura

```
prompts/      templates de system prompt (base: arranjos-casa v1.1; canalizadores é variante)
clients/      output por cliente: variables.json, deploy.json (demo incluído)
webhooks/     FastAPI: tools, eventos Retell, SQLite, relatório diário
scripts/      setup_retell.py — cria/atualiza o agente demo (idempotente, --dry-run)
tests/        pytest (correr com: uv run pytest)
docs/         PLANO-POC, ARQUITETURA, SETUP, pitch/ (guião + material visual)
.claude/agents/  subagentes do onboarding
```

## Convenções

- Tudo em PT-PT (código comentado em inglês é aceitável; prompts e docs sempre PT-PT).
- Secrets só em `.env` (ver `.env.example`). Nunca em git — manter `.env` no `.gitignore`.
- Python 3.12 + FastAPI + uvicorn; gestor de pacotes: uv.
- Os nomes dos tools (`notificar_tecnico`, `registar_recado`, `consultar_agenda`, `marcar_servico`) estão referenciados no prompt e no `scripts/setup_retell.py` — não renomear sem atualizar ambos os lados.
- Webhooks respondem <1s: trabalho lento (SMS, escritas) vai para background tasks.
- Todos os endpoints Retell verificam a assinatura `X-Retell-Signature`.

## Regras de negócio invioláveis (compliance PT/UE)

1. O agente identifica-se como IA na abertura de TODAS as chamadas (AI Act).
2. Aviso de gravação na abertura (RGPD).
3. Nunca prometer hora exata de chegada nem preço fechado — apenas "a partir de X, o técnico confirma".
4. Fuga de gás → instruções de segurança + indicar 112 se cheiro forte.

## Estado do trabalho

Ver `HANDOFF.md` — contém o estado, decisões e próximos passos. Retomar sempre a partir daí.
