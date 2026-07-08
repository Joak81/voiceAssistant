# voice-onboard

Negócio de atendimento telefónico por IA fora de horas (AI receptionist) para PMEs portuguesas. Nicho inicial: canalizadores/eletricistas. Este repo contém (a) os assets por cliente na Retell AI e (b) o agente de onboarding que automatiza a criação de cada novo cliente.

## Arquitetura

- **Plataforma de voz:** Retell AI (agente, voz, número, telefonia). Docs: https://docs.retellai.com
- **Webhooks (este repo):** FastAPI em `webhooks/` a correr no Mac Mini — recebe as custom functions do agente e o evento pós-chamada.
- **Marcações:** Cal.com (ou Google Calendar) via tool calling.
- **Notificações:** Twilio SMS para o dono do negócio (urgências) + relatório diário às 8h por email.
- **Onboarding:** comando `/onboard <url>` → subagentes em `.claude/agents/` (scraper → prompt-builder → deployer → qa).

## Estrutura

```
prompts/      templates de system prompt (base: canalizadores)
clients/      output por cliente: prompt.md, variables.json, deploy.json
webhooks/     FastAPI: notificar_tecnico, consultar_agenda, marcar_servico, resumo_chamada
.claude/agents/  subagentes do onboarding
```

## Convenções

- Tudo em PT-PT (código comentado em inglês é aceitável; prompts e docs sempre PT-PT).
- Secrets só em `.env` (RETELL_API_KEY, TWILIO_SID, TWILIO_TOKEN, CALCOM_API_KEY, WEBHOOK_BASE_URL). Nunca em git — manter `.env` no `.gitignore`.
- Python 3.12 + FastAPI + uvicorn; gestor de pacotes: uv.
- Os nomes das 4 custom functions estão referenciados no prompt — não renomear sem atualizar ambos os lados.

## Regras de negócio invioláveis (compliance PT/UE)

1. O agente identifica-se como IA na abertura de TODAS as chamadas (AI Act).
2. Aviso de gravação na abertura (RGPD).
3. Nunca prometer hora exata de chegada nem preço fechado — apenas "a partir de X, o técnico confirma".
4. Fuga de gás → instruções de segurança + indicar 112 se cheiro forte.

## Estado do trabalho

Ver `HANDOFF.md` — contém o estado, decisões e próximos passos. Retomar sempre a partir daí.
