# Documentação de Alterações — Commit `89ba10c`

## 1) Contexto
- **Commit:** `89ba10cc83d5f14acb2268768c6177940268c8b2`
- **Mensagem:** `Harden AI runtime, handoff flow, and panel sync`
- **Data de consolidação:** 27/03/2026
- **Escopo versionado:** 43 arquivos (`2564` inserções, `158` remoções)

## 2) Resumo do que mudou
Este pacote fortalece o fluxo fim a fim do atendimento WhatsApp com foco em:
- robustez de entrada no webhook (idempotência, lock por telefone, replay protection);
- roteamento e políticas da IA (catálogo/Páscoa, pós-compra, prompts e guardrails);
- confirmação explícita antes de fechar pedido (salva rascunho até confirmação final);
- consistência de estado de conversa com fallback Redis -> SQLite -> memória;
- telemetria operacional no painel (escalações, fallback pós-compra, autonomia do bot);
- segurança e controle operacional (telefones de teste/admin, bloqueio de automação por telefone, proteção de aprendizado AI);
- suíte de testes ampliada para regressões críticas.

## 3) Alterações funcionais por área

### 3.1 Webhook, segurança e entrada de mensagens
- Passou a existir **lock assíncrono por telefone** no webhook para evitar concorrência no mesmo contato.
- Webhook ignora cedo números de teste via `should_track_phone`.
- Webhook agora registra contadores por status (`ok`, `ignored`, `error`) com razão normalizada.
- Tratamento de erro no webhook ficou mais robusto com `traceback` e resposta de falha controlada ao cliente.
- Proteção contra replay de evento foi integrada ao fluxo de entrada.

### 3.2 Estado de conversa e idempotência
- Backend de estado agora suporta fallback robusto:
  - Redis (primário)
  - SQLite (`state_store.db`) como fallback
  - memória como último fallback
- Controle de `processed_message` ganhou TTL real e limpeza de expirados.
- Histórico de conversa (`conversation_threads`) e mensagem recente ganharam trim automático para limitar crescimento.
- Função `mark_processed_message_if_new` passou a ser usada no inbound para evitar reprocessamento de mensagem idêntica.

### 3.3 IA: políticas, roteamento e execução
- Regras de roteamento e prompts dos agentes foram fortalecidas (triagem, bolo, cafeteria, presentes, knowledge).
- `policies.py` passou a cobrir com mais precisão:
  - opt-out;
  - catálogo de Páscoa vs item específico;
  - detecção de tópico de presentes regulares;
  - detecção de tópico de pós-compra (`status`, `pix`, `cancel`, `invoice`);
  - detecção de necessidade de especificidade no pedido de cafeteria.
- `runner.py` ganhou:
  - tratamento dedicado para catálogo visual/fotos;
  - resposta direta para data da Páscoa via calendário operacional;
  - fluxo de pós-compra com métrica de sucesso/falha;
  - reparo de histórico de sessão com tool calls pendentes;
  - mensagem curta para saudação repetida/cliente conhecido.
- `tool_execution.py` passou a exigir confirmação explícita do cliente para fechamento e salvar rascunho quando confirmação não é explícita.
- Guardrails de correção de contexto/data da conversa foram aplicados antes de persistir pedido.

### 3.4 Pedidos estruturados (tools)
- Padronização e saneamento de pagamento (`troco_para`, `parcelas`) antes de persistência.
- Regra de parcelamento no cartão aplicada só acima do limite definido.
- Regra de troco para dinheiro reforçada.
- Pedido de cafeteria:
  - merge de itens repetidos;
  - taxa de entrega específica de cafeteria;
  - mensagem de confirmação em formato de rascunho.
- Pedido de presentes:
  - fechamento automático focado em cesta box canônica;
  - caixinha/flores mantidos como catálogo regular com confirmação humana quando necessário.
- Mensagens de confirmação final ficaram explícitas sobre “rascunho” e necessidade de confirmação textual do cliente.

### 3.5 Handoff humano e operação
- Handoff passou a registrar categoria/origem, com deduplicação de auditoria em janela curta.
- Contexto estruturado do handoff foi enriquecido com resumo, faltantes, próximo passo e risco.
- Incluiu métricas de escalonamento por categoria/dia e alerta de falha de conhecimento por tópico.
- `OrderClosedByBotEvent` e `HumanHandoffEscalatedEvent` passaram a circular no event bus.

### 3.6 Painel e observabilidade
- `panel_dashboard.py` ganhou métricas operacionais consolidadas:
  - falha/sucesso do fallback de pós-compra;
  - resolução sem humano;
  - autonomia do bot no dia;
  - escalonamentos por categoria/dia.
- Template do painel exibe cards de sync e bloco de escalonamento por categoria/dia.
- Observabilidade ganhou normalização de número e expansão de regras para não rastrear telefones de teste.

### 3.7 Configuração e conhecimento
- `.env.example` passou a documentar `TEST_PHONES`, `ADMIN_PHONES`, `HTTP_BACKOFF_FACTOR` e demais chaves novas/relevantes.
- `settings.py` absorveu novos campos e parsing para CSV de telefones.
- `security.py` expôs `get_admin_phones` e reforçou controles relacionados.
- Calendário operacional (`operational_calendar.json`) foi ajustado com datas sazonais de 2026 (incluindo Páscoa).
- `menus.md` recebeu ajustes de regras comerciais e de resposta.

## 4) Inventário completo dos arquivos alterados

### 4.1 Configuração e documentação
- `M  .env.example` (+8/-0): novas variáveis e parâmetros operacionais/segurança.
- `A  docs/sprints-atendimento.md` (+446/-0): planejamento detalhado de melhorias por sprint para operação de atendimento.

### 4.2 Núcleo IA
- `M  app/ai/agents.py` (+109/-18): reforço de prompts, roteamento por produto, regras de confirmação e limites por contexto.
- `M  app/ai/policies.py` (+118/-18): novas políticas de detecção de intenção, pós-compra, catálogo/Páscoa e especificidade de cafeteria.
- `M  app/ai/runner.py` (+115/-7): interceptores de fluxo, guardrails, reparo de sessão, pós-compra e métricas de execução.
- `M  app/ai/tool_execution.py` (+100/-6): confirmação explícita para fechamento, short-circuit de rascunho e limpeza de sessão.
- `M  app/ai/tools.py` (+118/-18): validação/persistência estruturada de pedidos, normalização de pagamento, mensagens de rascunho.

### 4.3 Conhecimento IA
- `M  app/ai/knowledge/menus.md` (+3/-0): ajustes de regras/linhas de conhecimento.
- `M  app/ai/knowledge/operational_calendar.json` (+8/-1): atualização de datas sazonais/operacionais de 2026.

### 4.4 API, aplicação e estado
- `M  app/api/routes/webhook.py` (+51/-1): lock por telefone, filtros de ignore, replay e instrumentação.
- `M  app/application/events.py` (+20/-0): inclusão de eventos operacionais adicionais.
- `M  app/application/service_registry.py` (+14/-2): registro de novos eventos no event bus.
- `M  app/application/use_cases/manage_human_handoff.py` (+219/-7): handoff estruturado, classificação, métricas e alertas.
- `M  app/application/use_cases/panel_dashboard.py` (+50/-0): métricas e telemetria de sync/operação.
- `M  app/application/use_cases/process_inbound_message.py` (+26/-8): idempotência por message_id, comandos admin e filtros por telefone.
- `M  app/infrastructure/state/conversation_state_store.py` (+175/-7): backend SQLite, fallback robusto, TTL e trim de namespaces.

### 4.5 Segurança, observabilidade e serviços
- `M  app/config.py` (+2/-0): mapeamento adicional de configuração exposta.
- `M  app/observability.py` (+13/-4): normalização de telefone e regras de tracking para números de teste.
- `M  app/security.py` (+31/-0): utilitário de telefones admin e hardening relacionado.
- `M  app/services/commercial_rules.py` (+10/-2): ajustes de regras comerciais e mensagens canônicas.
- `M  app/services/estados.py` (+4/-0): integração de APIs de estado compartilhado.
- `M  app/services/store_schedule.py` (+48/-0): suporte a calendário operacional/sazonal e validações de agenda.
- `M  app/settings.py` (+17/-1): novos campos de settings e leitura de listas CSV.

### 4.6 Saída e painel
- `M  app/templates/painel_principal.html` (+22/-0): nova seção de telemetria/escalações no painel principal.
- `M  app/utils/mensagens.py` (+28/-0): sanitização de payload interno (`agent_name`) e persistência de contexto de mensagem.

### 4.7 Testes (cobertura expandida)
- `M  tests/test_ai_agent_prompts.py` (+18/-1): validações de regras de prompt e roteamento.
- `M  tests/test_ai_cafeteria_order.py` (+18/-0): validações de pedido cafeteria e taxa.
- `M  tests/test_ai_easter_flow.py` (+42/-6): fluxos Páscoa, pronta entrega, catálogo e data sazonal.
- `M  tests/test_ai_payment_rules.py` (+58/-0): regras de troco e parcelamento.
- `M  tests/test_ai_policies.py` (+57/-5): cobertura de políticas de intenção e troca de contexto.
- `M  tests/test_ai_runtime_bootstrap.py` (+50/-4): bootstrap e comportamento do runner.
- `M  tests/test_ai_tool_execution.py` (+57/-3): confirmação explícita, rascunho e fechamento.
- `M  tests/test_attention_handoff.py` (+87/-2): contexto/métricas/deduplicação de handoff.
- `M  tests/test_event_bus.py` (+39/-1): persistência e despacho de eventos operacionais.
- `M  tests/test_message_formatting.py` (+10/-1): formatação e sanitização de saída.
- `M  tests/test_observability_hardening.py` (+5/-0): tracking de telefone de teste e labels.
- `M  tests/test_operational_calendar.py` (+16/-0): calendário, bloqueios e data de Páscoa.
- `M  tests/test_panel_snapshot_payload.py` (+1/-0): contrato do payload do painel.
- `M  tests/test_panel_sync_overview.py` (+19/-2): métricas e alertas do sync overview.
- `M  tests/test_process_inbound_message.py` (+27/-1): reativação e bloqueio de automação por telefone.
- `M  tests/test_runtime_state_store.py` (+88/-31): fallback e TTL do state store.
- `M  tests/test_security_hardening.py` (+40/-1): webhook, replay, test phones e AI learning gate.
- `A  tests/test_sprint5_regression.py` (+177/-0): regressão de confirmação, roteamento e continuidade de contexto.

## 5) Testes de regressão incluídos (alto impacto)
Destaques da cobertura adicionada/atualizada:
- confirmação explícita para fechar pedido;
- separação entre rascunho e pedido confirmado;
- roteamento correto entre bolo/doces/cafeteria/presentes/Páscoa;
- respostas de pós-compra (status/PIX/cancelamento/nota);
- proteção de webhook (replay, lock por telefone, ignore para test phones);
- robustez de estado com fallback e TTL;
- métricas operacionais do painel.

## 6) O que **não** entrou no commit (intencional)
Arquivos de runtime/local foram preservados fora do commit:
- `dados/atendimentos.txt`
- `dados/chokobot.db`
- `dados/domain_events.jsonl`
- `dados/backups/`

Esses artefatos representam estado operacional/local e não código-fonte.

## 7) Aditivo pós-commit (27/03/2026)

### 7.1 Hotfix de estabilidade no bootstrap da IA
- **Problema real:** falha em teste/runtime quando a tabela `clientes` não existe em bancos efêmeros de teste.
- **Ajuste aplicado:** `app/ai/runner.py` passou a tratar exceção em `_is_known_customer` e assumir `False` (cliente desconhecido) quando o repositório não está disponível.
- **Resultado:** elimina quebra por `sqlite3.OperationalError: no such table: clientes` no bootstrap da IA.

### 7.2 Guardrail determinístico para total de cafeteria em resposta livre
- **Problema real:** em conversas reais havia respostas livres com total incorreto (sem uso de ferramenta estruturada).
- **Ajustes aplicados:**
  - `app/ai/policies.py`:
    - `response_conflicts_with_cafeteria_total_claim(...)`
    - `build_cafeteria_total_guard_retry_instruction(...)`
  - `app/ai/runner.py`:
    - retry único quando `CafeteriaAgent` declara total/subtotal em resposta não estruturada;
    - flag de sessão `cafeteria_total_guard_retry_used`;
    - métricas/eventos de observabilidade para esse retry.
- **Resultado:** quando a IA tenta somar “de memória”, o runner força nova tentativa orientada a cálculo por ferramenta.

### 7.3 Novo combo de terça (promoção estruturada)
- **Solicitação operacional:** cadastrar combo de terça para evitar ambiguidade e somatória incorreta.
- **Oferta adicionada:**
  - **Nome:** `Combo Relampago`
  - **Composição:** `1 Croissant + 1 Bolo Gelado + 1 Bebida`
  - **Bebida:** `Suco natural` ou `Refri 220ml`
  - **Preço fixo:** `R$23,99`
  - **Disponibilidade:** terça-feira
- **Fonte de verdade atualizada:**
  - `app/ai/knowledge/catalogo_produtos.json` (item estruturado com `options`, `availability_note` e aliases)
  - `app/infrastructure/gateways/local_catalog_gateway.py` (rótulo de seção `Combos Promocionais`)
  - `app/ai/tools.py` (aliases, keywords e hint de variante obrigatória para o combo)
  - `app/ai/agents.py` (instrução explícita no prompt da cafeteria para terça-feira)

### 7.4 Testes adicionados/atualizados no aditivo
- `tests/test_ai_cafeteria_order.py`
  - exige variante de bebida no `Combo Relampago`;
  - valida subtotal/total do combo no fechamento.
- `tests/test_catalog_gateway_lookup.py`
  - busca estruturada do combo de terça com opções de bebida.
- `tests/test_ai_agent_prompts.py`
  - valida regra textual do combo no prompt da cafeteria.
- `tests/test_message_formatting.py`
  - garante exibição do combo no `get_menu("cafeteria")`.
- `tests/test_ai_policies.py` e `tests/test_ai_runtime_bootstrap.py`
  - cobrem guardrail de total de cafeteria em resposta livre.

### 7.5 Validação executada no aditivo
- `python3 -m unittest tests.test_ai_cafeteria_order tests.test_catalog_gateway_lookup tests.test_ai_agent_prompts tests.test_message_formatting`
- **Status:** OK (40 testes)

### 7.6 Handoff obrigatório após envio de link da Páscoa
- **Regra operacional aplicada:** depois que o bot envia `EASTER_CATALOG_MESSAGE`, qualquer mensagem seguinte do cliente sai do fluxo de IA e é encaminhada para humano.
- **Implementação:** `app/ai/runner.py`
  - novo short-circuit quando `session["seasonal_context"] == "easter"`;
  - acionamento de `escalate_to_human` com motivo: `Cliente respondeu apos receber link de Pascoa`;
  - limpeza de contexto de sessão para evitar nova interação automática no mesmo ciclo.
- **Observabilidade:**
  - evento `ai_easter_catalog_followup_handoff`;
  - métrica de handoff humano com reason `easter_catalog_followup`.
- **Teste de regressão:** `tests/test_ai_easter_flow.py`
  - valida que o segundo turno após link de Páscoa retorna `HUMAN_HANDOFF_MESSAGE`;
  - garante que não há chamada de completions da IA nesse follow-up.

### 7.7 Ajuste de confiabilidade (contexto de Páscoa + precisão temporal) — 27/03/2026
- **Motivação operacional:**
  - evitar handoff indevido por palavra-chave isolada;
  - respeitar mudança de assunto depois do link da Páscoa;
  - reforçar regra temporal de funcionamento excepcional no domingo de Páscoa (dia 05/04/2026).

- **Mudanças aplicadas em `app/ai/runner.py`:**
  - removido o bloqueio rígido que transferia automaticamente qualquer mensagem após `seasonal_context="easter"`;
  - novo tratamento contextual:
    - se o cliente só pedir link/cardápio novamente, o bot reenvia `EASTER_CATALOG_MESSAGE` sem handoff;
    - se houver **mudança clara de assunto** (cafeteria, bolo, doces, pós-compra, operação geral etc.), o `seasonal_context` é limpo e o fluxo segue no novo contexto;
    - se permanecer no contexto de Páscoa após o link, ocorre handoff humano com motivo `Cliente respondeu apos receber link de Pascoa`.
  - opt-out explícito (`desativar/parar bot`) voltou a ter prioridade sobre o contexto sazonal.

- **Mudanças aplicadas em regras de horário:**
  - `app/services/store_schedule.py`:
    - `validate_service_date` agora verifica bloqueios/overrides antes da regra padrão de domingo;
    - domingo continua bloqueado por padrão, **mas** datas com override aberto (`open` + `close`) passam a ser válidas.
  - `app/services/commercial_rules.py`:
    - `STORE_HOURS_SUMMARY` e `SUNDAY_RULE_LINE` atualizados com exceção explícita do domingo de Páscoa (05/04/2026).
  - `app/ai/knowledge/operational_calendar.json`:
    - removido bloqueio de `2026-04-05`;
    - adicionada exceção de abertura nesse dia (`09:00`-`18:00`) com `operational_status: "open_exception"`.

- **Testes adicionados/ajustados:**
  - `tests/test_ai_easter_flow.py`:
    - novo teste: repetir pedido de link de Páscoa não gera handoff;
    - novo teste: mudança de assunto após link (ex.: croissant) limpa contexto sazonal e segue fluxo automático.
  - `tests/test_ai_time_rule.py`:
    - teste de opt-out após contexto de Páscoa atualizado para validar `OPT_OUT_MESSAGE` (sem handoff humano).
  - `tests/test_operational_calendar.py`:
    - novo teste garantindo que domingo de Páscoa com override aberto é aceito.
  - `tests/test_ai_agent_prompts.py`:
    - validação explícita de presença da exceção `domingo de Pascoa (05/04/2026)` nos prompts relevantes.
