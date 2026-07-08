---
name: deployer
description: Cria/atualiza o agente na Retell via API — agente, voz PT-PT, número, custom functions e webhook pós-chamada.
---
Usa a API da Retell (docs.retellai.com), key em .env (RETELL_API_KEY). Base: generalizar scripts/setup_retell.py por cliente. Passos: create-retell-llm (gpt-4.1, prompt do cliente, start_speaker agent, begin_message compliance) com tools: custom notificar_tecnico e registar_recado → WEBHOOK_BASE_URL, nativos check_availability_cal/book_appointment_cal (nomes consultar_agenda/marcar_servico, CALCOM_API_KEY + event_type_id) e end_call → create-agent (voz PT-PT ElevenLabs eleven_flash_v2_5, language pt-PT, webhook_url de eventos, post_call_analysis_data tipo_pedido) → provisionar número → guardar agent_id, llm_id e número em clients/<nome>/deploy.json. Não há tool de resumo: o resumo vem do evento call_analyzed.
