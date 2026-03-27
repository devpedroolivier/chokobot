# Sprints — Melhoria de Atendimento Trufinha Bot
> Base para uso com agente de código. Organizado por prioridade de impacto.
> Fonte: análise de conversas reais (fev–mar 2026) — ver `docs/whatsapp-conversation-ops-audit.md`

---

## Sprint 1 — Bugs Críticos de Sistema

**Objetivo:** Eliminar falhas que tornam o bot inutilizável ou que expõem a estrutura interna ao cliente.

---

### S1-1 Bug de sessão: saudação enviada múltiplas vezes

**Problema:** O bot reenvia a mensagem de boas-vindas para o mesmo cliente durante a conversa, como se fosse um primeiro contato. Em alguns casos a mesma mensagem foi enviada 4–5 vezes em sequência dentro de segundos.

**Causa provável:** Condição de corrida no processamento do webhook — múltiplos disparos do mesmo evento chegam antes de a sessão ser persistida no Redis.

**Arquivos relevantes:**
- `app/infrastructure/state/` — gestão de sessão
- `app/api/routes/webhook.py` — entrada do webhook
- `app/application/handlers/` — handler de mensagem recebida
- `app/ai/runner.py` — runner OpenAI

**Tarefas:**
- [ ] Identificar onde a sessão é lida/escrita no fluxo de mensagem recebida
- [ ] Adicionar lock ou flag de "sessão ativa" para evitar reinicialização enquanto conversa em andamento
- [ ] Garantir que deduplicação por `message_id` está funcionando antes de qualquer processamento
- [ ] Testar com envio rápido de 3–4 mensagens em sequência (< 2s entre elas)

---

### S1-2 Bug de contexto: histórico perdido entre mensagens

**Problema:** O bot trata cada mensagem como se fosse um novo atendimento, ignorando o que foi discutido anteriormente na mesma conversa. Clientes precisam repetir a intenção várias vezes.

**Arquivos relevantes:**
- `app/infrastructure/state/` — armazenamento do histórico por telefone
- `app/ai/runner.py` — carregamento do histórico antes de chamar a LLM
- `app/application/commands/generate_reply.py` (ou similar)

**Tarefas:**
- [ ] Verificar se o histórico de mensagens está sendo carregado corretamente antes de cada chamada à LLM
- [ ] Confirmar que o TTL do Redis para histórico não está expirando prematuramente
- [ ] Verificar se o fallback in-memory (quando Redis indisponível) está mantendo o contexto entre requests
- [ ] Adicionar log de diagnóstico indicando quantas mensagens de histórico foram carregadas por chamada
- [ ] Criar teste de integração: enviar 5 mensagens em sequência e validar que a 5ª resposta referencia o contexto das anteriores

---

### S1-3 JSON interno de roteamento exposto ao cliente

**Problema:** O bot enviou ao cliente a string `{ "agent_name": "CakeOrderAgent" }` como parte da resposta de texto. Isso expõe a arquitetura interna e é profissionalmente inadequado.

**Arquivos relevantes:**
- `app/ai/agents.py` — definição dos agentes e da tool `transfer_to_agent`
- `app/ai/runner.py` — processamento de tool calls e formatação da resposta final

**Tarefas:**
- [ ] Identificar onde o payload de transferência de agente pode vazar para o texto de resposta
- [ ] Garantir que o conteúdo de tool calls (`transfer_to_agent`) nunca é concatenado ao texto enviado ao cliente
- [ ] Adicionar sanitização na camada de output: qualquer string contendo `{` e `"agent_name"` deve ser removida antes do envio
- [ ] Testar o fluxo de roteamento e confirmar que mensagem de transição ao cliente é apenas o texto amigável configurado

---

### S1-4 Respostas duplicadas enviadas ao cliente

**Problema:** Em várias conversas o bot enviou a mesma resposta duas vezes seguidas (ex: Alzi, Rafa Bertone, Eduarda Gaisdorf). Correlacionado ao S1-1 mas pode ter causa independente.

**Arquivos relevantes:**
- `app/api/routes/webhook.py`
- `app/infrastructure/gateways/zapi.py` (ou equivalente de envio)
- `app/application/handlers/`

**Tarefas:**
- [ ] Verificar se o webhook Z-API pode disparar o mesmo evento duas vezes (retry automático)
- [ ] Implementar cache de `message_id` já processado com TTL de 60s para idempotência
- [ ] Verificar se o handler de mensagem está sendo chamado mais de uma vez por evento
- [ ] Adicionar log de alerta quando a mesma `message_id` chegar mais de uma vez

---

### S1-5 Filtrar número de teste da fila de atendimento

**Problema:** O número `5511888888888` gerou mais de 70 escalações falsas no período, completamente poluindo a fila de atendimento humano e impossibilitando a análise de métricas reais.

**Arquivos relevantes:**
- `app/config.py` ou `app/settings.py` — variáveis de ambiente
- `app/api/routes/webhook.py` — entrada principal
- `.env.example`

**Tarefas:**
- [ ] Criar variável de ambiente `TEST_PHONES` (lista separada por vírgula)
- [ ] No handler de webhook, ignorar ou rotear para modo sandbox qualquer mensagem de número na lista `TEST_PHONES`
- [ ] Garantir que escalações de números de teste não aparecem em `dados/atendimentos.txt`
- [ ] Documentar em `.env.example` o uso de `TEST_PHONES`

---

## Sprint 2 — Catálogo de Produtos e Roteamento de Agentes

**Objetivo:** Fazer o bot atender corretamente os produtos que ele já deveria saber vender.

---

### S2-1 Ovos de Páscoa: configurar suporte completo

**Problema:** Durante o período mais importante do ano para uma confeitaria, o bot recusou sistematicamente pedidos de ovos de Páscoa com a mensagem "não está no contexto de confeitaria". O catálogo (`catalogo_produtos.json`) possui os produtos.

**Arquivos relevantes:**
- `app/ai/agents.py` — agentes e seus system prompts
- `app/ai/knowledge/menus.md` — fonte principal do LLM
- `app/ai/knowledge/catalogo_produtos.json` — catálogo com itens de Páscoa
- `app/services/commercial_rules.py` — regras comerciais

**Tarefas:**
- [ ] Verificar se os itens de Páscoa de `catalogo_produtos.json` estão sendo carregados no contexto do agente
- [ ] Atualizar `menus.md` com seção explícita de produtos sazonais de Páscoa (ovos, trufados, trios, pré-lançamentos)
- [ ] Definir qual agente é responsável por pedidos de ovos de Páscoa (`GiftOrderAgent` ou novo `EasterAgent`)
- [ ] Atualizar o system prompt do `TriageAgent` para incluir intent de Páscoa no roteamento
- [ ] Criar regra no `TriageAgent`: pedidos de ovos de Páscoa prontos → escalar para humano (pronta entrega); ovos por encomenda → `GiftOrderAgent`
- [ ] Testar com frases: "quero um ovo de páscoa", "tem ovo trufado?", "cardápio de ovos", "trio de páscoa"

---

### S2-2 GiftOrderAgent: cestas, caixas e flores

**Problema:** O bot promete explicitamente na saudação que pode ajudar com "Presentes especiais (cestas, caixas ou flores)", mas escala todos esses pedidos para humano imediatamente.

**Arquivos relevantes:**
- `app/ai/agents.py` — `GiftOrderAgent` e `TriageAgent`
- `app/ai/knowledge/catalogo_presentes_regulares.json`
- `app/ai/knowledge/catalogo_produtos.json`

**Tarefas:**
- [ ] Auditar o system prompt do `GiftOrderAgent` — identificar por que não está sendo invocado ou por que escala
- [ ] Confirmar que `catalogo_presentes_regulares.json` está no contexto do `GiftOrderAgent`
- [ ] Mapear quais combinações de presentes o bot pode fechar sozinho vs. quais precisam de humano
- [ ] Atualizar roteamento do `TriageAgent` para reconhecer: "cesta", "caixa de chocolate", "flores", "presente", "mimo"
- [ ] Se `GiftOrderAgent` ainda não tiver fluxo de fechamento, implementar coleta mínima: produto + data + modalidade (retirada/entrega)
- [ ] Remover da saudação o que o bot não consegue atender, ou fazer o bot atender de fato

---

### S2-3 SweetOrderAgent: doces avulsos

**Problema:** Pedidos de brigadeiros, bombons e doces avulsos estão sendo escalados. O `SweetOrderAgent` existe mas não parece ser ativado corretamente.

**Arquivos relevantes:**
- `app/ai/agents.py` — `SweetOrderAgent` e `TriageAgent`
- `app/ai/knowledge/menus.md` — seção de doces

**Tarefas:**
- [ ] Auditar o roteamento do `TriageAgent` para doces avulsos
- [ ] Testar com frases: "quero brigadeiros", "tem docinhos?", "quanto custa bombom?", "10 brigadeiros de ninho"
- [ ] Verificar se o `SweetOrderAgent` coleta corretamente: tipo do doce, quantidade, data de retirada/entrega
- [ ] Confirmar que pedidos de doces para hoje (pronta entrega) são tratados corretamente
- [ ] Confirmar que pedidos de fotos de doces direcionam ao link de catálogo, não à escalação

---

### S2-4 CafeteriaAgent: combos de croissant e itens de vitrine

**Problema:** Pedidos explícitos de "2 combos de croissant de peito de Peru com coca normal" ficaram em loop sem resolução. O bot não finalizou o pedido em nenhuma das 3 tentativas do cliente.

**Arquivos relevantes:**
- `app/ai/agents.py` — `CafeteriaAgent`
- `app/ai/knowledge/menus.md` — seção cafeteria
- `app/ai/knowledge/catalogo_produtos.json` — itens de cafeteria

**Tarefas:**
- [ ] Auditar fluxo completo do `CafeteriaAgent` para pedidos de combo
- [ ] Verificar se os combos disponíveis (croissant + bebida) estão descritos no knowledge base
- [ ] Implementar fluxo de fechamento: item + quantidade + modalidade + horário de retirada
- [ ] Testar: "quero 1 combo croissant de frango", "2 combos croissant peito de peru com coca", "tem croissant hoje?"
- [ ] Garantir que o agente registra o pedido em `pedidos_cafeteria` no banco

---

## Sprint 3 — Informações Críticas de Negócio

**Objetivo:** O bot deve ter e fornecer as informações que os clientes precisam para fechar um pedido.

---

### S3-1 Chave PIX: obrigatória no fluxo de pagamento

**Problema:** O bot recusou ativamente fornecer a chave PIX quando um cliente disse "vou fazer o pagamento". Isso bloqueia vendas concluídas. PIX é um dos principais meios de pagamento da loja.

**Arquivos relevantes:**
- `app/ai/knowledge/menus.md` — seção de pagamento
- `app/ai/agents.py` — policy de informações de pagamento
- `app/config.py` ou `app/settings.py`

**Tarefas:**
- [ ] Adicionar chave PIX ao knowledge base do bot (pode ser configurada via env var `PIX_KEY`)
- [ ] Remover qualquer instrução que impeça o bot de compartilhar informações de pagamento
- [ ] Atualizar system prompt para incluir etapa de pagamento no fluxo de fechamento: após confirmar pedido, oferecer as formas de pagamento e informar a chave PIX se solicitado
- [ ] Testar: "qual o PIX?", "como pago?", "manda o PIX", "pode ser PIX?"

---

### S3-2 Data de Páscoa e informações sazonais corretas

**Problema:** O bot informou que a Páscoa era "dia 09 de abril" quando era dia 5. Datas incorretas geram desconfiança.

**Arquivos relevantes:**
- `app/ai/knowledge/operational_calendar.json` — feriados e datas
- `app/services/store_schedule.py`

**Tarefas:**
- [ ] Auditar `operational_calendar.json` para garantir que a data da Páscoa está correta
- [ ] Verificar se o bot usa essa fonte de dados ou se tem a data hardcoded em algum prompt
- [ ] Criar mecanismo de atualização fácil de datas sazonais (idealmente via `operational_calendar.json` sem necessidade de redeploy)
- [ ] Adicionar testes de regressão para datas: bot deve responder corretamente à "quando é a Páscoa?"

---

### S3-3 Link de catálogo visual como resposta padrão para pedidos de foto

**Problema:** Quando clientes pedem fotos dos produtos, o bot diz que não pode enviar e não oferece nenhuma alternativa. Venda trava.

**Arquivos relevantes:**
- `app/ai/agents.py` — todos os agentes de produto
- `app/ai/knowledge/menus.md`
- `.env.example`

**Tarefas:**
- [ ] Criar variável de ambiente `CATALOG_LINK` (Instagram, site ou link de PDF do catálogo)
- [ ] Atualizar os system prompts de todos os agentes de produto para: quando cliente pedir foto, responder com o link do catálogo e convidar a ver as fotos por lá
- [ ] Testar: "tem foto?", "me manda uma foto", "posso ver como fica?", "tem imagem?"

---

### S3-4 Informação de reserva/pedido online correta

**Problema:** O bot disse ao cliente "Não fazemos reservas por telefone ou online. Você pode vir à loja". Isso contradiz a própria existência do bot.

**Arquivos relevantes:**
- `app/ai/agents.py` — `CakeOrderAgent`, `KnowledgeAgent`
- `app/ai/knowledge/menus.md`

**Tarefas:**
- [ ] Remover qualquer instrução que diga que pedidos só são aceitos presencialmente
- [ ] Atualizar menus.md para deixar explícito que pedidos podem ser feitos pelo WhatsApp
- [ ] Garantir que o `KnowledgeAgent` responde corretamente: "como faço um pedido?", "posso reservar pelo WhatsApp?"

---

### S3-5 Cardápio completo disponível sem escalação

**Problema:** Quando cliente pede "cardápio de bolos com tamanho e preço", o bot transfere para um "especialista" em vez de simplesmente responder com o cardápio que já possui.

**Arquivos relevantes:**
- `app/ai/agents.py` — `KnowledgeAgent`, `TriageAgent`
- `app/ai/knowledge/menus.md`

**Tarefas:**
- [ ] Garantir que o `KnowledgeAgent` tem o cardápio completo de bolos com tamanhos e preços
- [ ] Atualizar o `TriageAgent` para rotear pedidos de cardápio ao `KnowledgeAgent` e não a um "especialista" indefinido
- [ ] Testar: "me manda o cardápio", "quais são os tamanhos de bolo?", "quanto custa um B6?", "tem torta?"

---

## Sprint 4 — Fluxo de Conversa e Experiência do Cliente

**Objetivo:** Melhorar a fluidez e naturalidade do atendimento, reduzindo atritos desnecessários.

---

### S4-1 Eliminar pergunta binária de entrada ("Pronta entrega ou Encomenda?")

**Problema:** A primeira pergunta do bot força o cliente a se encaixar numa categorização interna que ele não conhece. Quem quer "um bolo de cenoura" ou "brigadeiros para amanhã" não pensa nesses termos.

**Arquivos relevantes:**
- `app/ai/agents.py` — `TriageAgent`, system prompt de abertura
- `app/ai/knowledge/menus.md`

**Tarefas:**
- [ ] Reescrever o `TriageAgent` para identificar a intenção pelo **produto** mencionado, não pela categoria
- [ ] Criar mapeamento explícito no prompt: "bolo" → `CakeOrderAgent`, "brigadeiro/doce" → `SweetOrderAgent`, "croissant/combo" → `CafeteriaAgent`, "cesta/presente/flor" → `GiftOrderAgent`
- [ ] Manter a pergunta "pronta entrega ou encomenda" apenas quando o contexto realmente exigir (ex: "quero um bolo" sem especificar quando)
- [ ] Testar com entradas diretas: "quero um B3 pra hoje", "brigadeiros para sábado", "tem croissant?"

---

### S4-2 Saudação única e não repetitiva

**Problema:** A saudação longa é enviada para clientes recorrentes e no meio de conversas ativas, gerando atrito.

**Arquivos relevantes:**
- `app/ai/agents.py` — `TriageAgent`
- `app/infrastructure/state/`

**Tarefas:**
- [ ] Verificar se o cliente já tem histórico de conversas e, se sim, usar saudação curta
- [ ] Implementar flag "cliente conhecido" com base em histórico no banco (`clientes` table)
- [ ] Para clientes recorrentes: "Olá [nome]! Como posso ajudar hoje? 😊" em vez da saudação completa
- [ ] Garantir que a saudação é enviada **no máximo uma vez por sessão** (ver S1-1)

---

### S4-3 Mensagem de escalação informativa

**Problema:** Quando o bot transfere para humano, diz apenas "Um momento! Estou transferindo você". O cliente não sabe se alguém vai responder, quando, nem o que foi entendido até ali.

**Arquivos relevantes:**
- `app/ai/agents.py` — mensagem de transferência padrão
- `app/services/store_schedule.py` — horários de funcionamento

**Tarefas:**
- [ ] Criar template de mensagem de escalação com: resumo do que foi entendido + expectativa de tempo de resposta
- [ ] Considerar horário ao escalar: se fora do horário comercial, informar que será respondido no próximo dia útil
- [ ] Exemplo de mensagem ideal: *"Entendi que você quer [resumo]. Vou passar para nossa equipe! Respondemos em até [X] minutos no horário comercial (ter–sáb, 09h–18h)."*

---

### S4-4 Upsell automático no fechamento do pedido

**Problema:** O bot faz upsell do Kit Festou apenas no fluxo de bolos. Não há ofertas complementares nos outros fluxos.

**Arquivos relevantes:**
- `app/ai/agents.py` — `CakeOrderAgent`, `SweetOrderAgent`, `CafeteriaAgent`

**Tarefas:**
- [ ] No `CakeOrderAgent`: manter oferta do Kit Festou (já existe), mas garantir que não é perguntado mais de uma vez
- [ ] No `SweetOrderAgent`: após definir doces, oferecer caixinha/embalagem especial se disponível
- [ ] No `CafeteriaAgent`: após pedido de croissant, oferecer bebida (se não incluída) ou item adicional
- [ ] Limitar upsell a **uma** oferta por pedido para não parecer insistente

---

### S4-5 Confirmação estruturada do pedido antes de fechar

**Problema:** Em algumas conversas o pedido ficou ambíguo (Natália queria doces, horário "17:15", mas não há registro de confirmação clara). Clientes saem sem saber se o pedido foi registrado.

**Arquivos relevantes:**
- `app/ai/agents.py` — todos os agentes de produto
- `app/infrastructure/repositories/` — criação de pedidos

**Tarefas:**
- [ ] Implementar etapa de confirmação explícita em todos os agentes de produto:
  ```
  "Confirma seu pedido?
  📦 [item] x[qtd]
  📅 [data/hora]
  🚗 [retirada/entrega + endereço se entrega]
  💰 Total: R$[valor]
  Forma de pagamento: [PIX/dinheiro/cartão]"
  ```
- [ ] Só registrar o pedido no banco após confirmação ("sim", "confirma", "pode ser", etc.)
- [ ] Após confirmação: enviar mensagem de encerramento com número de protocolo ou resumo salvo

---

## Sprint 5 — Observabilidade e Qualidade Operacional

**Objetivo:** Criar instrumentação para monitorar a saúde do atendimento e medir o impacto das melhorias.

---

### S5-1 Classificação de motivos de escalação

**Problema:** Hoje é impossível distinguir escalações legítimas (cliente pediu humano) de falhas do bot (produto não reconhecido) de ruído (spam). Os KPIs estão completamente distorcidos.

**Arquivos relevantes:**
- `dados/atendimentos.txt` — log atual
- `app/application/` — emissão de eventos
- `app/infrastructure/` — repositórios

**Tarefas:**
- [ ] Definir categorias de escalação: `cliente_solicitou`, `produto_fora_escopo`, `falha_bot`, `spam_fora_contexto`, `assumido_painel`
- [ ] Atualizar o evento de escalação para incluir categoria além do motivo textual
- [ ] Criar métrica Prometheus `escalacao_total{categoria=}` no endpoint `/metrics`
- [ ] Adicionar ao painel admin uma visão de escalações por categoria por dia

---

### S5-2 Taxa de fechamento autônomo de pedidos

**Problema:** Não existe hoje uma métrica de quantos pedidos o bot fecha de ponta a ponta sem intervenção humana. Sem isso, é impossível medir melhoria.

**Arquivos relevantes:**
- `dados/domain_events.jsonl` — eventos de domínio
- `app/application/events.py`
- Endpoint `/metrics`

**Tarefas:**
- [ ] Criar evento `OrderClosedByBot` emitido quando um pedido é confirmado sem escalação no mesmo fluxo
- [ ] Criar métrica `pedido_fechado_autonomo_total` vs `pedido_escalado_total`
- [ ] Calcular taxa de autonomia: `fechado_bot / (fechado_bot + escalado)` por dia
- [ ] Expor no painel admin com tendência histórica

---

### S5-3 Alertas para falhas recorrentes

**Problema:** Falhas como o PIX bloqueado ou Páscoa fora de escopo ficaram semanas sem ser detectadas porque não há alerta automático.

**Arquivos relevantes:**
- `app/ai/agents.py` — geração de resposta
- `app/infrastructure/` — monitoramento
- Endpoint `/metrics`

**Tarefas:**
- [ ] Criar detector de padrão: se mais de X escalações por motivo similar em 1h, emitir alerta no log com nível `WARNING`
- [ ] Criar métrica `falha_conhecimento_total{topico=}` para rastrear tópicos que o bot não consegue responder
- [ ] Considerar webhook de alerta para canal interno (Slack, email, WhatsApp admin) quando taxa de escalação superar threshold configurável

---

### S5-4 Testes de regressão de fluxo de atendimento

**Problema:** As falhas identificadas (PIX, Páscoa, contexto perdido) não foram detectadas por testes automatizados.

**Arquivos relevantes:**
- `tests/` — suíte existente
- `scripts/run_tests.py`

**Tarefas:**
- [ ] Criar testes de ponta a ponta para cada fluxo crítico:
  - [ ] Bolo B3 pronta entrega → confirmação → PIX
  - [ ] Doces brigadeiro → quantidade → data → confirmação
  - [ ] Pedido de ovo de Páscoa → roteamento correto
  - [ ] Pedido de cesta → `GiftOrderAgent` ativado
  - [ ] Pedido de combo cafeteria → fechamento
  - [ ] Múltiplas mensagens em sequência → contexto mantido
  - [ ] Pedido de foto → link do catálogo retornado
- [ ] Adicionar esses testes ao CI (GitHub Actions) para rodar em cada PR
- [ ] Criar teste de carga leve: 10 conversas simultâneas sem sessão contaminada

---

## Backlog — Melhorias Futuras

> Itens validados como valiosos mas sem urgência imediata.

- **Captura de nome do cliente**: perguntar o nome na primeira interação caso não identificado pelo perfil do WhatsApp; armazenar em `clientes`
- **Notificação pré-entrega**: quando pedido com entrega for confirmado, enviar lembrete automático 30min antes do horário registrado
- **Resposta fora do horário comercial**: no domingo (fechado) e após 18h, enviar mensagem informando horário de reabertura em vez de responder normalmente
- **Cancelamento de pedido**: o bot hoje não tem fluxo de cancelamento — cliente que cancela é escalado (`motivo=Cliente deseja cancelar uma encomenda`); criar fluxo básico de cancelamento com confirmação e registro
- **Consulta de status de pedido**: clientes perguntam "cadê meu pedido?" e são escalados; criar tool de consulta ao banco por telefone do cliente
- **Chave PIX como variável de configuração**: hoje está hardcoded ou ausente — tornar configurável via `.env` sem necessidade de redeploy
- **Cardápio sazonal automático**: integração com `operational_calendar.json` para que o bot saiba automaticamente quais produtos estão disponíveis em cada data/período
- **Integração com painel**: quando bot fecha pedido, criar automaticamente o registro no painel admin sem necessidade de entrada manual
