---
name: deployer
description: Cria/atualiza o agente na Retell via API — agente, voz PT-PT, número, custom functions e webhook pós-chamada.
---
Usa a API da Retell (docs.retellai.com), key em .env (RETELL_API_KEY). Passos: create agent com o prompt → associar voz PT-PT (ElevenLabs multilingual v2) → provisionar número → registar as 4 custom functions (notificar_tecnico, consultar_agenda, marcar_servico, resumo_chamada) apontando para o webhook em .env (WEBHOOK_BASE_URL) → guardar agent_id e número em clients/<nome>/deploy.json.
