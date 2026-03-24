# Auditoria do Fluxo WhatsApp -> Painel

## Objetivo

Consolidar uma leitura profunda do fluxo de conversa do WhatsApp ate o painel operacional da Chokobot, com foco em:

- contexto e intencao do cliente
- fronteira entre atendimento, rascunho e pedido confirmado
- sincronizacao entre runtime, banco e painel
- gargalos operacionais
- riscos de performance e de experiencia do cliente

## Data de referencia

- Auditoria executada em 2026-03-24

## Escopo auditado

- `app/api/routes/webhook.py`
- `app/application/use_cases/process_inbound_message.py`
- `app/application/use_cases/process_delivery_flow.py`
- `app/application/use_cases/process_cafeteria_flow.py`
- `app/application/use_cases/manage_human_handoff.py`
- `app/application/use_cases/panel_dashboard.py`
- `app/ai/tool_execution.py`
- `app/ai/tools.py`
- `app/infrastructure/state/conversation_state_store.py`
- artefatos em `dados/atendimentos.txt`, `dados/domain_events.jsonl` e `dados/chokobot.db`

## Resumo do fluxo atual

### 1. Entrada no webhook

O webhook normaliza a mensagem, filtra grupo/callback/replay e publica `MessageReceivedEvent` antes do processamento principal.

Implicacao:

- a trilha de eventos registra tentativas de inbound mesmo quando o fluxo posterior rejeita a mensagem como duplicada

### 2. Processamento inbound

Em `process_inbound_message.py`, qualquer mensagem valida:

- salva ou atualiza `cliente` por telefone
- tenta deduplicar por `message_id`
- tenta deduplicar por conteudo recente em janela curta
- respeita handoff humano se o telefone estiver em `estados_atendimento`
- so depois chama a IA

Implicacao:

- `cliente` continua significando "contato conhecido", nao "cliente com pedido"

### 3. Atendimento em andamento

O painel de WhatsApp e a tela de operacoes leem estados de runtime:

- `ai_sessions`
- `estados_encomenda`
- `estados_cafeteria`
- `estados_cestas_box`
- `estados_entrega`
- `estados_atendimento`
- `recent_messages`

Implicacao:

- atendimento depende de memoria/Redis, nao de trilha de negocio persistida

### 4. Confirmacao e persistencia

Existem dois modelos convivendo:

- fluxos mais guiados, como entrega e cesta, salvam processo antes e pedido depois da confirmacao
- flows de IA salvam rascunho em `customer_processes` quando falta confirmacao explicita e salvam pedido final apenas depois da confirmacao

Implicacao:

- a direcao do codigo esta melhor que a materializacao real no banco

### 5. Painel operacional

O board de pedidos confirmados continua lendo `encomendas` + `entregas`.

Implicacao:

- pedido confirmado e operacao ainda dependem mais da persistencia final do que da trilha de processo

## Evidencias observadas

### Banco real

Contagens observadas em `dados/chokobot.db`:

- `clientes`: 1525
- `customer_processes`: 0
- `encomendas`: 146
- `entregas`: 138
- `pedidos_cafeteria`: 0

Leitura:

- ha forte persistencia de contatos e pedidos
- nao ha trilha persistida de processo no banco auditado
- o painel de atendimento depende de runtime quase por completo no estado atual observado

### Handoff humano

`dados/atendimentos.txt` mostra 167 linhas.

Foi observado um padrao de repeticao forte para o mesmo telefone no dia 2026-03-23, com varias linhas de:

- `cliente pediu ajuda`

Leitura:

- o handoff humano esta sendo reativado/auditado varias vezes para o mesmo contato
- isso gera ruido operacional e dificulta distinguir um unico caso de varias ocorrencias reais

### Eventos de dominio

`dados/domain_events.jsonl` possui:

- `MessageReceivedEvent`: 1360
- `AiReplyGeneratedEvent`: 719
- `OrderCreatedEvent`: 14

Observacoes:

- ha `message_id` repetidos no outbox, especialmente `msg-2` com 17 ocorrencias
- o evento inbound e persistido antes da deduplicacao completa do caso de negocio
- ha `OrderCreatedEvent` com `order_id = -1` para cafeteria

Leitura:

- a trilha de eventos nao representa apenas eventos de negocio validos; ela mistura tentativa, duplicidade e erro sem contrato forte

## Gargalos principais

### 1. Runtime e banco nao compartilham a mesma verdade de processo

O codigo usa `customer_processes` como trilha de atendimento/rascunho, mas o banco auditado esta vazio nessa tabela.

Consequencia:

- o painel de atendimento depende de estado transitivo
- reinicio de runtime ou troca de instancia tende a apagar a leitura operacional em andamento
- atendimento e pedido nao compartilham uma chave persistida unica

### 2. Handoff humano gera ruido e auditoria repetida

`activate_human_handoff` audita toda ativacao, e o artefato real mostra repeticao intensa para o mesmo caso.

Consequencia:

- fila humana pode parecer mais volumosa do que realmente e
- dificil separar novos casos de reaberturas do mesmo contato

### 3. Outbox de eventos registra duplicatas e eventos fracos

O webhook publica `MessageReceivedEvent` antes do processamento inbound consolidado. Alem disso, cafeteria publica `OrderCreatedEvent` com `order_id = -1`.

Consequencia:

- a trilha de eventos nao e boa fonte para auditoria confiavel de negocio
- qualquer futura automacao orientada a evento herdara ruido

### 4. Conexao WhatsApp -> painel ainda e parcialmente acidental

Hoje a visibilidade no painel nasce de fontes diferentes:

- runtime para atendimento
- `encomendas`/`entregas` para operacao
- eventualmente `customer_processes` no codigo, mas nao no banco observado

Consequencia:

- o operador ve duas realidades que nao necessariamente se explicam entre si

### 5. Fluxo de cafeteria continua fraco como entidade operacional

`process_cafeteria_flow.py` confirma o pedido de cafeteria e persiste auditoria/evento, mas:

- nao grava `pedidos_cafeteria` com id de pedido operacional reutilizavel
- publica `OrderCreatedEvent` sintetico com `order_id = -1`
- a tabela real `pedidos_cafeteria` esta vazia no banco auditado

Consequencia:

- cafeteria ainda nao entra de forma forte e rastreavel na mesma linguagem operacional dos demais pedidos

### 6. Pedidos sem entrega correspondente ainda existem

Foram observadas 8 encomendas sem linha correspondente em `entregas`.

Leitura:

- parte pode ser historico ou legado
- ainda assim, o modelo operacional segue permitindo pedido existir sem trilha logistica correspondente

## Impacto na experiencia do cliente

### O que o cliente provavelmente percebe

- confirmacao nem sempre tem uma fronteira visivel e consistente
- handoff humano pode acontecer varias vezes sem sensacao clara de continuidade
- alguns assuntos fora do escopo ou ambiguidade levam cedo ao humano
- a conversa ativa nao necessariamente deixa rastro operacional persistido

### O que precisa melhorar na interacao

- resumo final mais consistente antes de pedir confirmacao
- menos caminhos que jogam para humano sem preservar contexto de negocio
- feedback mais claro sobre "pedido em rascunho", "aguardando confirmacao" e "pedido confirmado"
- transicao melhor entre bot e humano, com menos reacendimentos repetidos do mesmo caso

## Impacto no painel e na operacao

### O que o operador ve hoje

- atendimento ativo via runtime
- pedidos confirmados via banco

### O que falta

- uma entidade persistida unica para dizer:
  - quem esta em atendimento
  - quem esta aguardando confirmacao
  - quem virou pedido
  - quem foi para handoff
  - quem converteu ou se perdeu

## Riscos de performance

### 1. Reconstrucao cara de estado

Como o painel de atendimento depende de estado transitivo e nao de uma tabela persistida de processo, ele precisa recompor a leitura operacional a partir de varios mapas e consultas auxiliares.

### 2. Eventos ruidosos

O outbox cresce com duplicatas de inbound e eventos de criacao fracos, o que dificulta qualquer analise posterior de gargalo real.

### 3. Fallback para memoria

`conversation_state_store.py` cai para memoria local quando Redis falha e o fallback esta habilitado.

Consequencia:

- o sistema segue funcionando
- mas a rastreabilidade e a sincronizacao entre instancias ficam piores justamente na parte de atendimento

## Melhorias recomendadas

### Curto prazo

1. Tornar `customer_processes` a trilha persistida minima e obrigatoria para atendimento ativo, rascunho, handoff e conversao.
2. Parar de emitir `OrderCreatedEvent` com `order_id = -1`.
3. Diferenciar no outbox:
   - inbound recebido
   - inbound aceito
   - inbound descartado por duplicidade
4. Reduzir reativacoes/auditorias repetidas de handoff para o mesmo telefone em janela curta.
5. Exibir no painel uma explicacao curta de origem do card:
   - runtime
   - processo persistido
   - pedido confirmado

### Medio prazo

1. Criar estado de negocio canonico:
   - `novo_contato`
   - `em_atendimento`
   - `rascunho`
   - `aguardando_confirmacao`
   - `handoff_humano`
   - `convertido`
   - `perdido`
2. Fazer a transicao para pedido confirmado sempre passar por essa trilha.
3. Unificar cafeteria no mesmo modelo de processo/pedido.
4. Garantir que toda encomenda operacional relevante tenha entrega/retirada correspondente.

### Longo prazo

1. Parar de depender de runtime como fonte primaria para o painel operacional.
2. Usar runtime apenas como apoio de conversa, nao como verdade de negocio.
3. Evoluir trilha de eventos para auditoria realmente confiavel de atendimento e conversao.

## Leitura final

O problema principal nao e "o WhatsApp nao conversa com o painel". O problema principal e que a conexao atual ainda mistura:

- contato
- atendimento
- rascunho
- pedido confirmado
- estado transitivo de runtime

No codigo, ja existe uma direcao correta para separar isso. No estado real auditado, essa separacao ainda nao se materializou de forma persistida.

Em termos praticos:

- o cliente entra
- o bot atende
- parte do contexto fica em runtime
- parte vira pedido
- o painel precisa inferir o resto

Enquanto `customer_processes` nao virar a trilha operacional minima de verdade, o painel continuara vendo uma combinacao de sinais, nao um fluxo de negocio unico.
