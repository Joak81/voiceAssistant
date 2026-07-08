# Handoff de sessão — voice-onboard
Data: 2026-07-08
Pasta de trabalho: raiz deste repo (sugerido: ~/dev/voice-onboard)
Branch / git: repo ainda não iniciado — `git init` pendente

## 1. Objetivo
Montar o negócio de atendimento telefónico por IA fora de horas ("AI receptionist") para PMEs portuguesas, começando pelo nicho canalizadores/eletricistas. Dois entregáveis: infraestrutura por cliente na Retell AI, e agente de onboarding em Claude Code que cria cada novo cliente em ~15 minutos (scrape do site → prompt → deploy → QA).

## 2. Estado atual
Planeamento concluído numa sessão claude.ai (08-07-2026): stack, pricing, go-to-market e script de vendas decididos. Primeiro artefacto produzido: system prompt v1.0 do agente demo (`prompts/prompt-agente-demo-canalizadores.md`). Skeletons dos 4 subagentes criados. Zero código escrito — o webhook é o próximo passo.

## 3. Já feito
- Plataforma escolhida: Retell AI (ver decisões abaixo).
- System prompt demo v1.0 em PT-PT com compliance embutido (identificação IA + aviso gravação), triagem urgência/normal, fluxos completos, FAQ e guardrails — `prompts/prompt-agente-demo-canalizadores.md`.
- Dynamic variables definidas: `nome_empresa`, `nome_agente`, `taxa_urgencia`, `zonas_atuacao`.
- Arquitetura do onboarding definida e skeletons criados: `.claude/agents/{scraper,prompt-builder,deployer,qa}.md`.
- Modelo de pricing, unit economics e script de vendas fechados (secção 5 e 9).
- `CLAUDE.md` com convenções e regras de negócio invioláveis.

## 4. Por fazer (próximos passos)
1. **Webhook `notificar_tecnico`** em `webhooks/` (FastAPI + Twilio SMS ao dono com nome, morada, telemóvel, problema). Começar por aqui.
2. Endpoint `resumo_chamada` (webhook pós-chamada da Retell) + agregação para relatório diário às 8h (launchd no Mac Mini, email ao dono).
3. Criar conta Retell, provisionar número demo PT, colar o prompt, registar as 4 custom functions a apontar para o webhook.
4. Integração Cal.com: `consultar_agenda` e `marcar_servico`.
5. Comando `/onboard <url>` completo, orquestrando os 4 subagentes.
6. Doc de onboarding do cliente (ativação do desvio condicional `**61*<número>#`).
7. Teste end-to-end com chamada real ao número demo.

## 5. Decisões e raciocínio
- **Retell AI** escolhida vs Vapi e Synthflow: $0,07/min sem platform fee, all-in real $0,07–0,12/min, RGPD/SOC2 nos planos standard, low-code + API completa, números a $2/mês. Vapi descartada: custo real $0,13–0,33/min e 4–5 fornecedores para gerir (STT/LLM/TTS/telefonia separados). Synthflow descartada: voice-only, $0,15–0,24/min, no-code que limita a automatização e mostra strain perto de 10k chamadas/mês.
- **Telefonia sem fricção:** o cliente mantém o número e ativa desvio condicional para o número do agente fora de horas. Nada a instalar.
- **Pricing:** setup €200–400 + tiers mensais Base €79 (atende, FAQ, recados) / Pro €129 (+ marcações) / Premium €179 (+ SMS follow-up, multi-idioma). Custo real por cliente €10–25/mês (100–200 min) → margem bruta >80%. 20 clientes ≈ €2.500 MRR.
- **GTM:** demo ao vivo — ligar ao negócio fora de horas na véspera; no dia seguinte, pitch "isto foi o que perdeu ontem" + número demo para ele ligar. Nichos por ordem de dor: canalizadores/eletricistas, clínicas dentárias/veterinários, restaurantes, oficinas. Lead gen: scraping Google Maps (horário limitado + reviews a queixar de não atenderem). Trial 14 dias sem risco.
- **Compliance (inviolável):** identificação como IA + aviso de gravação na abertura (AI Act + RGPD); nunca prometer hora exata nem preço fechado; fuga de gás → instruções de segurança + 112. Já embutido no prompt — não remover.
- **LLM do agente:** manter modelo rápido (GPT-4o-mini ou Haiku) para latência <800ms; latência acima disso quebra a conversa telefónica.

## 6. Ficheiros relevantes
- `prompts/prompt-agente-demo-canalizadores.md` — prompt v1.0 pronto a colar na Retell; é também o template base do prompt-builder.
- `.claude/agents/scraper.md`, `prompt-builder.md`, `deployer.md`, `qa.md` — skeletons a expandir; o contrato entre eles (JSON do scraper → variables do builder → deploy.json) está descrito em cada um.
- `CLAUDE.md` — convenções, estrutura, regras de negócio.
- `webhooks/` — vazio; alvo do passo 1.

## 7. Comandos úteis
- Ainda não há build; quando o webhook existir: `uv run uvicorn webhooks.main:app --reload --port 8000`.
- Docs Retell (API, custom functions, webhook pós-chamada): https://docs.retellai.com
- Expor o Mac Mini para a Retell em dev: usar o túnel habitual via Tailscale funnel (ou cloudflared).

## 8. Problemas em aberto / armadilhas
- **Vozes PT-PT:** testar vozes femininas da ElevenLabs multilingual v2 na Retell; evitar vozes PT-BR para este público — validar com chamada de teste antes de qualquer demo.
- Os nomes das 4 custom functions estão hard-coded no prompt (`notificar_tecnico`, `consultar_agenda`, `marcar_servico`, `resumo_chamada`) — renomear implica atualizar prompt e Retell em simultâneo.
- Vapi/Retell mudam pricing com frequência (tiers movem-se trimestralmente) — confirmar valores atuais antes de fechar o pricing final aos clientes.
- Webhook tem de responder rápido (<1–2s) ou o agente fica em silêncio na chamada — responder já e processar async.

## 9. Contexto a preservar (snippets / valores)
- Custos por componente (referência jul/2026): STT $0,005–0,02/min · LLM $0,02–0,10/min · TTS ~$0,04/min · telefonia ~$0,01/min.
- Código de desvio condicional (qualquer operador PT): `**61*<número do agente>#` (desviar se não atender); desativar: `##61#`.
- Gancho de abertura do script de vendas: "Ontem às 21h40 liguei para a vossa empresa e ninguém atendeu. Eu não era cliente a sério — mas se fosse, hoje o serviço era do vosso concorrente."
- Respostas a objeções: máquinas → "Preferem uma máquina que resolve a um voicemail que ninguém ouve"; voicemail → "não distingue urgência, não marca serviço, a maioria desliga"; caro → "uma urgência recuperada paga dois meses".
- Fecho: "Levo 15 minutos a pôr isto a funcionar. Quer que fique ativo já esta noite?"

## 10. Como retomar
Cola isto numa sessão nova do Claude Code na raiz do projeto:
"Lê o HANDOFF.md e o CLAUDE.md. Não recomeces o que está em 'Já feito'. Confirma comigo o passo 1 de 'Por fazer' e avança."
(Alternativa compatível com a tua skill: `cp HANDOFF.md ~/.claude/handoffs/latest.md` e depois `/handoff retomar`.)
