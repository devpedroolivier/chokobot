# Changelog — Demandas 2026-04-23

Entrega dos itens P0/P1 do documento
[TODO_DEMANDAS_2026-04-23.md](TODO_DEMANDAS_2026-04-23.md).

## O que mudou

### 1. Envio de mensagens pelo painel (P0)

- Mapeamento de erros do backend para mensagens explicativas no composer e no
  toggle de automação em `frontend/src/components/inbox.tsx`
  (`BACKEND_ERROR_LABELS`, `extractBackendError`).
- Mensagens `admin_session_required`, `frontend_proxy_not_configured`,
  `message_send_failed`, `invalid_backend_response` e `message_required` agora
  aparecem no painel em português com dica do que verificar (Z-API, env,
  sessão).
- **Nota operacional:** se `PANEL_BACKEND_URL` ou `ADMIN_SESSION_SECRET` não
  estiverem configurados no Next.js, o erro agora é explícito.

### 2. Captura imediata de conversas (P0)

- `build_whatsapp_cards` (em `app/application/use_cases/panel_dashboard.py`)
  passa a considerar `conversation_threads` como fonte de telefones. Qualquer
  número que mandou mensagem aparece no inbox assim que o webhook processar,
  mesmo sem processo ativo ou estado legado.
- Nova `stage_label` `"Conversa aberta"` para cards sem processo associado.
- Cards mantêm `last_seen` e `last_message` com base no thread quando não há
  `recent_messages`.
- O `AutomationToggle` continua ativando/desativando o chat por conversa para
  esses cards (via `/painel/api/conversas/{phone}/automation`).

### 3. Templates de atendente (P1)

- Novo env `PANEL_ATTENDANTS` (default `Lu`) exposto via snapshot do painel.
- `MessageComposer` ganha dropdown de atendente (persistido em
  `localStorage`) e três templates prontos:
  - Apresentação: "Oi! Aqui é {atendente} da Chokodelícia 🍫 …"
  - Assumir chat: "Oi! A Trufinha me chamou aqui, sou a {atendente} …"
  - Pedir um minuto: "Aqui é {atendente}. Me dá um minutinho que já te
    respondo, tá?"

### 4. Contexto da Trufinha — ocasião e nº de pessoas (P1)

- `CAKE_ORDER_PROMPT` em `app/ai/agents.py` recebe:
  - **Regra 4.0**: coletar ocasião (aniversário, casamento, chá de bebê,
    mesversário, corporativo) e nº de pessoas **antes** de recomendar linha
    ou tamanho.
  - Pergunta padronizada: "Pra te sugerir o tamanho certo, me conta rapidinho:
    é pra qual ocasião e mais ou menos quantas pessoas vão comer?"

### 5. Regra de tamanho por nº de pessoas (P1)

- **Regra 4.1** no prompt e nova seção em `app/ai/knowledge/menus.md` com a
  tabela definitiva:
  - Até 8 pessoas: P4, Linha Simples ou B3.
  - 9–20 pessoas: P6, Gourmet Inglês ou B3/B4.
  - 21–30 pessoas: prioriza B4 retangular.
  - **>30 pessoas: prioriza B6 (até 50p) ou B7 (até 80p).**
  - **Limite rígido: P4/P6 nunca para mais de 20 pessoas.** (Regra 4.2)
- Agente orienta a oferecer "dois bolos menores" ou trocar para retangular
  caso o cliente insista em redondo grande.

### 6. Agendamento Trufinha sex 19h ↔ seg 06h (P1)

- Novas envs em `app/settings.py`:
  `AI_AUTO_SCHEDULE_ENABLED`, `AI_AUTO_OFF_WEEKDAY/HOUR/MINUTE`,
  `AI_AUTO_ON_WEEKDAY/HOUR/MINUTE`.
- Função `ai_auto_schedule_state()` em `app/services/store_schedule.py`
  devolve `{active, enabled, off_label, on_label}` por minuto-da-semana.
- `process_inbound_message` não invoca o runner OpenAI dentro da janela
  inativa; ainda registra a mensagem em `conversation_threads` + cria o
  cliente, para que o painel mostre o que chegou.
- Snapshot do painel expõe `store_pulse.ai_schedule` e o inbox mostra um pill
  `"Trufinha ativa · off Sex 19:00"` / `"Trufinha pausada · volta Seg 06:00"`.
- Defaults cobrem **sex 19h → seg 06h** — incluindo todo sábado. Se o cliente
  quiser sábado com bot ativo, mudar `AI_AUTO_OFF_WEEKDAY=5` + ajustar hora.

## Como testar

1. **Suite automatizada:**
   ```bash
   python3 scripts/run_tests.py
   ```
   318 testes devem passar. Testes novos:
   - `tests/test_ai_auto_schedule.py` (8 testes de fronteira da janela).
   - `tests/test_panel_whatsapp_cards.py::test_conversation_only_card_appears_for_fresh_phone`.

2. **Painel — envio de mensagem:**
   - Abra uma conversa, digite e envie.
   - Se `PANEL_BACKEND_URL` ausente: verá `"PANEL_BACKEND_URL não configurada
     no frontend."` diretamente.
   - Se Z-API recusar: `"Z-API recusou a mensagem. Verifique ZAPI_TOKEN/
     ZAPI_BASE…"`.

3. **Painel — captura imediata:**
   - Mande mensagem de um número que **não tem cadastro nem pedido**.
   - Em até 5 s (polling) a conversa aparece com stage "Conversa aberta".
   - Toggle de IA deve funcionar normalmente.

4. **Painel — templates de atendente:**
   - Abra uma conversa. No composer, selecione o atendente (dropdown).
   - Clique em "Apresentação", "Assumir chat" ou "Pedir um minuto".
   - O nome escolhido é injetado no template e persiste entre sessões.

5. **Trufinha — ocasião e tamanho (manual, smoke):**
   - Cliente: "Quero um bolo pra sábado" → bot pergunta ocasião + pessoas.
   - Cliente: "Aniversário pra 40 pessoas" → bot sugere B6/B7, nunca P4/P6.
   - Cliente: "Quero P6 pra 30 pessoas" → bot recusa e explica o limite.

6. **Agendamento (manual):**
   - Ajustar relógio ou env para sexta 19h: painel mostra "Trufinha pausada".
   - Mensagens nesse período não recebem resposta da IA, mas aparecem no
     inbox e criam o cliente.

## Riscos e pontos de atenção

- **Sábado sem IA (default):** a janela `sex 19h → seg 06h` cobre sábado
  inteiro, dia em que a loja está aberta (09–18). Se o cliente não quiser
  isso, ajustar env `AI_AUTO_OFF_WEEKDAY=5` + `AI_AUTO_OFF_HOUR=22` (por
  exemplo), ou redesenhar a janela em múltiplas faixas.
- **Timezone:** `ai_auto_schedule_state` usa `BOT_TIMEZONE`
  (`America/Sao_Paulo`). Se o ambiente de deploy estiver em UTC e o env não
  propagar, o cálculo pode deslocar 3h.
- **Polling 5 s:** o inbox continua em polling. Para "imediatismo" real,
  migrar para SSE/WebSocket — fora do escopo dessa entrega.
- **Histórico acumulado:** conversation_only cards antigos (>24 h) são
  filtrados pelo corte existente. Conversas recentes após pedido convertido
  **continuam visíveis** (novo comportamento validado pelo teste
  `test_contact_to_confirmation_moves_from_whatsapp_flow_to_panel_order`).

## Arquivos tocados

- `app/settings.py` — envs de schedule + atendentes.
- `app/services/store_schedule.py` — `ai_auto_schedule_state`,
  `is_ai_within_schedule`, `build_store_pulse.ai_schedule`.
- `app/application/use_cases/process_inbound_message.py` — guard da janela.
- `app/application/use_cases/panel_dashboard.py` — source
  `conversation_only`, thread fallback em `last_seen`/`last_message`.
- `app/api/routes/painel.py` — expõe `attendants` no snapshot.
- `app/ai/agents.py` — prompt com regras 4.0 / 4.1 / 4.2.
- `app/ai/knowledge/menus.md` — tabela de tamanho por nº de pessoas.
- `frontend/src/components/inbox.tsx` — error surfacing, AI schedule pill,
  dropdown de atendente, templates.
- `frontend/src/lib/panel-types.ts` — `AiSchedulePulse`, `attendants`.
- `frontend/src/lib/panel-api.ts` — propaga `attendants`.
- `.env.example` — novas envs documentadas.
- `tests/test_ai_auto_schedule.py` (novo).
- `tests/test_panel_whatsapp_cards.py` (+1 teste).
- `tests/test_whatsapp_e2e_panel_flow.py` (expectativa ajustada).
