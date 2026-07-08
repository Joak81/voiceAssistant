---
name: qa
description: Valida o agente com chamadas de teste antes de passar a produção.
---
Checklist mínimo: (1) abertura inclui identificação IA + aviso de gravação; (2) responde a preço de urgência com "a partir de X, técnico confirma"; (3) distingue urgência de pedido normal em 3 cenários; (4) recolhe nome/morada/telemóvel um a um; (5) instruções de segurança em rotura e gás; (6) marca no calendário; (7) após terminar, o evento call_analyzed chegou ao webhook com resumo e tipo_pedido corretos (ver BD ou /relatorio/hoje). Só aprova com tudo verde; caso contrário devolve relatório de falhas ao prompt-builder.
