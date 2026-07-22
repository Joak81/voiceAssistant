# Número português (+351) — estado, caminhos e custos

Investigação verificada a 22-07-2026 (fontes oficiais + Wayback do catálogo Twilio; afirmações críticas verificadas adversarialmente).

## O que aconteceu na Twilio (o mistério resolvido)

- Portugal **esteve** no catálogo self-service da Twilio durante anos: PT Local a $1/mês (até ~2024-25) e PT Mobile a $15/mês (ainda no snapshot do CSV oficial de 08-03-2026). É por isso que há quem tenha comprado +351 na consola sem fricção.
- **Entre 08-03-2026 e 22-07-2026, Portugal foi removido do catálogo self-service** (confirmado por diff dos CSVs oficiais no Wayback: o CSV atual tem 57 países, sem PT). O 404 em `/AvailablePhoneNumbers/PT/*` significa "sem inventário exposto à conta" — não é problema do bundle nem da conta.
- A única oferta PT publicada hoje é premium: **"Clean Mobile Numbers" a $135/mês** + $0,0107/min inbound (era $15/mês em março — 9× mais caro).
- Nada disto se resolve com planos/tiers (só mudam SLAs de suporte), nem com região IE1 (números compram-se sempre via US1), nem com toggles na consola (consola e API self-service mostram o mesmo inventário).
- Porting para a Twilio: **só toll-free +351800** — números geográficos/móveis PT não são portáveis para lá.

## Caminho oficial na Twilio (se se quiser insistir)

**Exclusive Number order / Private Offering** — para números fora do catálogo:
1. Consola → Phone Numbers → Buy a Number → botão **"Can't find a Number?"** (canto superior direito) → formulário; ou diretamente https://twlo.my.salesforce-sites.com/PrivateOffering ; ou ticket ao Support.
2. Fornecer: Account SID, **Bundle SID aprovado**, Address SID, tipo (Mobile), quantidade (1), prefixo desejado (+3519, opcional).
3. Revisão ~3 dias úteis; entrega típica 1–4 semanas. A API não suporta estes números; a compra conclui-se pela equipa de inventário.
4. **Perguntar o preço no pedido** — se for os $135/mês listados, é incomportável para o modelo (€79-179/mês por cliente).

Dados desta conta (não commitados — obter na consola Twilio):
- Account SID: consola → Account Dashboard (formato `ACxxxx…`)
- Bundle SID (Mobile-Individual, aprovado): Regulatory Compliance → Bundles (formato `BUxxxx…`)
- Address SID (PT, validada): Phone Numbers → Regulatory Compliance → Addresses (formato `ADxxxx…`)

## Caminho recomendado para o negócio: fornecedor DID barato + SIP para a Retell

Enquanto a Twilio não voltar a ter PT em self-service a preço razoável:
- **Zadarma** (particulares OK: ID + morada; ~€2–5/mês) ou **DIDWW** (premium) vendem +351 móvel/geográfico.
- Ligação à Retell por **"Dial to SIP URI"** (docs oficiais, Method 2): o fornecedor encaminha para `sip:{call_id}@sip.retellai.com` (o call_id vem do Register Phone Call API — endpoint nosso no Railway a devolver o encaminhamento). Telefonia Retell: $0,00/min (custom telephony).
- Com número Twilio (se o exclusive order compensar): **Elastic SIP Trunking** → import na Retell (`POST /import-phone-number` com termination URI + credenciais; origination `sip:sip.retellai.com`; allowlist CIDR `18.98.16.120/30`; trunking inbound PT ≈ $0,0067/min). Geo permissions de voz: ativar PT e US no seletor Elastic SIP Trunking; atenção: transfers para móveis PT devem originar do +351 (desde EEA $0,0455/min vs $0,491/min fora).

## Custos comparados (número +351, mensal)

| Via | Custo/mês | Notas |
|---|---|---|
| Twilio Clean Mobile | ~$135 | preço público atual; incomportável por cliente |
| Twilio exclusive order | ? (perguntar) | pode ser diferente do público |
| Zadarma | ~€2–5 | particulares OK; Dial-to-SIP |
| DIDWW | ~€5–15 | qualidade operador; SIP trunk |
| Telnyx | ~$1 | **só empresas** (NIF + certidão + representante) — usar quando houver empresa |

## Novidades Twilio 2025-26 relevantes (plano B de arquitetura)

- **ConversationRelay** (GA mai-2025): `<Connect><ConversationRelay>` → websocket nosso; a Twilio trata STT (Google pt-PT) e TTS (ElevenLabs Flash 2.5, com voz default pt-PT) + barge-in; $0,07/min + voz; latência mediana ~0,49s. O nosso servidor custom-LLM (webhooks/grok_llm.py) adapta-se conceptualmente.
- **Agent Connect** (GA mai-2026): SDK Python/FastAPI por cima do ConversationRelay — o caminho certo se um dia sairmos da Retell. (Twilio AI Assistants foi descontinuado em jul-2026; Conversational Intelligence é só observabilidade, $0,027/min.)
- Comparação honesta: custo all-in semelhante à Retell (~$0,09–0,13/min); perderíamos tools nativos Cal.com, call_analyzed e dashboard Retell → **manter Retell na POC**; ConversationRelay documentado como plano B anti lock-in.
- Oportunidade: candidatura ao **Twilio AI Startup Searchlight 2026** (até set-2026) — até $5.000 em créditos Twilio + $2.500 OpenAI; a demo do voice-onboard encaixa no perfil.

## Fontes principais

- CSV catálogo: assets.cdn.prod.twilio.com/pricing-csv/SiteNumbersPricing.csv (+ snapshots Wayback 07-2024 / 11-2025 / 03-2026)
- help.twilio.com/articles/223183068 (availability; upd. 15-06-2026) · 223135247 (buy a number; upd. 29-06-2026) · 4404399659803 (Portugal Porting; upd. 17-07-2026)
- twilio.com/en-us/voice/pricing/pt · twilio.com/en-us/guidelines/pt/regulatory
- docs.retellai.com/deploy/custom-telephony (SIP trunk + Dial to SIP URI)
- twilio.com docs/blog: ConversationRelay, Agent Connect, Compliance Embeddable
