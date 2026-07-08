---
name: prompt-builder
description: Gera o system prompt Retell de um novo cliente a partir do JSON do scraper e do template base.
---
Template base: prompts/prompt-agente-demo-arranjos-casa.md (v1.1, nicho alargado; prompt-agente-demo-canalizadores.md é variante setorial). Substitui as dynamic variables, adapta a triagem e os serviços ao setor do cliente, preenche as FAQ com os dados reais. NUNCA remover: identificação como IA na abertura, aviso de gravação, regra de não prometer hora exata nem preço fechado. Output: clients/<nome>/prompt.md + variables.json.
