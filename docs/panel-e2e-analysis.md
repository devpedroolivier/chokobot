# Analise Aprofundada do Painel e do Fluxo E2E

## Objetivo

Este documento consolida a leitura operacional do painel interno da Chokobot e define a base para as melhorias de implementacao.

O foco aqui nao e atendimento ao cliente final. O foco e o uso interno do negocio:

- acompanhar conversas em andamento
- diferenciar contato/cliente de pedido confirmado
- monitorar pedidos ate entrega ou retirada
- sincronizar atendimento e painel operacional

## Resumo Executivo

Hoje o sistema mistura tres entidades de negocio diferentes:

1. `contato/cliente`
2. `atendimento em andamento`
3. `pedido confirmado`

Essa mistura gera ruido no painel porque:

- qualquer mensagem valida ja cria ou atualiza um cliente
- a area de WhatsApp do painel mostra estados de runtime, nao pedidos
- alguns fluxos persistem encomenda cedo demais, antes da confirmacao final
- o banco nao tem uma camada propria para representar `rascunho`, `orcamento` ou `aguardando confirmacao`

Resultado pratico:

- o time interno pode ver sinais de "pedido" quando ainda existe apenas intencao ou coleta de dados
- o painel de operacao e o fluxo de atendimento nao compartilham um estado de negocio unico

## Como o Fluxo Funciona Hoje

### 1. Primeiro contato

Assim que uma mensagem inbound valida entra, o sistema normaliza a mensagem e salva/atualiza o cliente por telefone.

Referencia:

- [process_inbound_message.py](/root/projects/chokobot/app/application/use_cases/process_inbound_message.py#L44)
- [process_inbound_message.py](/root/projects/chokobot/app/application/use_cases/process_inbound_message.py#L106)

Conclusao:

- `cliente` hoje significa "contato conhecido"
- `cliente` nao significa "pedido realizado"

### 2. Atendimento em andamento

O painel de WhatsApp nao le pedidos do banco. Ele junta estados transitivos de runtime:

- `ai_sessions`
- `estados_encomenda`
- `estados_cafeteria`
- `estados_cestas_box`
- `estados_entrega`
- `estados_atendimento`

Referencia:

- [panel_dashboard.py](/root/projects/chokobot/app/application/use_cases/panel_dashboard.py#L178)

Conclusao:

- essa area representa conversas/processos ativos
- nao deve ser tratada como fonte de verdade para pedidos confirmados

### 3. Pedido confirmado

O painel operacional de pedidos le apenas `encomendas` e `entregas`.

Referencia:

- [sqlite_order_repository.py](/root/projects/chokobot/app/infrastructure/repositories/sqlite_order_repository.py#L8)

Conclusao:

- o board de operacao so deveria mostrar pedidos realmente persistidos
- se o pedido aparece cedo demais, o problema esta no momento da persistencia

## Problema Central

O schema atual nao separa estados de negocio.

Referencia:

- [schema.sql](/root/projects/chokobot/app/db/schema.sql#L5)

Hoje existem:

- `clientes`
- `encomendas`
- `entregas`

Mas nao existem entidades para:

- lead
- atendimento ativo
- pedido em rascunho
- aguardando confirmacao
- orcamento sem fechamento

Sem essa camada intermediaria, a aplicacao acaba usando:

- runtime state para representar processo
- `encomendas` para representar pedido salvo

## Pontos Criticos do Fluxo

### Fluxo legado de entrega salva cedo demais

No fluxo legado, `_iniciar_entrega` preparava o pedido e persistia a encomenda antes da coleta completa de endereco e antes da confirmacao final de entrega.

Referencia:

- [encomendas.py](/root/projects/chokobot/app/services/encomendas.py#L167)

Esse era o principal ponto de falso positivo operacional.

### Flows com confirmacao melhor definida

O fluxo de `cesta_box` salva o pedido apenas depois da confirmacao e pagamento.

Referencia:

- [process_cesta_box_flow.py](/root/projects/chokobot/app/application/use_cases/process_cesta_box_flow.py#L122)

Esse fluxo esta mais alinhado com o que o painel precisa.

### Flows via IA ainda persistem diretamente

As tools de IA `create_cake_order` e `create_sweet_order` persistem pedido quando a tool e chamada.

Referencia:

- [tools.py](/root/projects/chokobot/app/ai/tools.py#L276)
- [tools.py](/root/projects/chokobot/app/ai/tools.py#L371)

Risco:

- se a IA acionar a tool cedo demais, o sistema nao tem uma camada de "confirmacao operacional" protegendo o painel

## Separacao de Conceitos Necessaria

### Entidade 1: Cliente/Contato

Representa:

- telefone
- nome
- historico de interacoes

Entra aqui:

- qualquer conversa valida

Nao implica:

- pedido fechado

### Entidade 2: Processo de atendimento

Representa:

- etapa atual da conversa
- intencao do cliente
- se esta montando um pedido
- se aguarda humano
- se houve abandono

Status sugeridos:

- `novo_contato`
- `em_atendimento`
- `montando_pedido`
- `aguardando_confirmacao`
- `handoff_humano`
- `convertido`
- `perdido`

### Entidade 3: Pedido

Representa:

- venda concluida ou formalmente assumida pela operacao

Status sugeridos:

- `rascunho`
- `confirmado`
- `em_producao`
- `pronto_retirada`
- `saiu_entrega`
- `concluido`
- `cancelado`

## Regra de Negocio Recomendada

### Quando deve aparecer em Atendimento

Mostrar no quadro de atendimento quando houver:

- conversa ativa
- estado de montagem de pedido
- aguardando resposta do cliente
- handoff para humano

### Quando deve aparecer em Pedidos

Mostrar no quadro operacional apenas quando houver confirmacao explicita.

Criterios minimos por tipo:

#### Retirada

- data definida
- horario definido
- forma de pagamento definida
- confirmacao final do cliente

#### Entrega

- data definida
- horario definido
- endereco definido
- forma de pagamento definida
- confirmacao final do cliente

Antes disso:

- deve ser atendimento
- pode ser rascunho/orcamento
- nao deve contaminar o board principal de producao

## Leitura do Painel Atual

### O que esta bom

- o dashboard principal ja traz no mesmo lugar cards de conversa e board operacional
- o kanban visual de pedidos tem boa base para operacao
- ha diferenciacao visual por urgencia, data e tipo

### O que esta ruim para a operacao

- atendimento e pedido nao compartilham uma chave/processo unico
- o quadro de pedidos nao sabe dizer se aquele pedido foi realmente confirmado ou apenas salvo
- a tabela de encomendas ainda e orientada a cadastro, nao a monitoramento
- `pendente` hoje cobre significados demais

## Modelo de Painel Recomendado

### Bloco 1: Atendimento Ativo

Objetivo:

- mostrar contatos em conversa ou em handoff

Campos:

- cliente
- etapa atual
- ultima mensagem
- tempo sem resposta
- origem do fluxo
- necessidade de acao humana

### Bloco 2: Aguardando Confirmacao

Objetivo:

- mostrar processos onde existe alta intencao de compra, mas o pedido ainda nao esta confirmado

Campos:

- cliente
- resumo do pedido
- falta endereco?
- falta pagamento?
- falta confirmacao final?

### Bloco 3: Pedidos Confirmados

Objetivo:

- mostrar apenas o que ja entrou na operacao

Campos:

- id
- cliente
- produto
- data/horario
- entrega vs retirada
- status de producao/logistica
- valor

### Bloco 4: Alertas

Objetivo:

- destacar anomalias

Exemplos:

- pedido salvo sem entrega
- pedido sem endereco e marcado como entrega
- atendimento parado ha muito tempo
- pedido antigo ainda em pendente

## Plano de Implementacao

### Fase 1: Corrigir falso positivo no fluxo legado

Objetivo:

- impedir que entrega apareca como pedido salvo antes da confirmacao final

Acoes:

- adiar persistencia da encomenda no fluxo legado de entrega
- manter apenas preview/estado ate confirmacao
- salvar `encomenda + entrega` apenas no `confirmar_entrega`

### Fase 2: Introduzir processo persistido

Objetivo:

- sincronizar atendimento e painel com uma entidade de negocio unica

Sugestao:

- criar `customer_process` ou `order_draft`

Campos minimos:

- `id`
- `phone`
- `customer_id`
- `process_type`
- `stage`
- `draft_payload`
- `is_confirmed`
- `converted_order_id`
- `updated_at`

### Fase 3: Separar visualmente atendimento de operacao

Acoes:

- area `Atendimento`
- area `Aguardando confirmacao`
- area `Pedidos confirmados`
- area `Hoje`

### Fase 4: Harden nas tools de IA

Acoes:

- separar tools de montagem/orcamento das tools de confirmacao
- impedir persistencia direta sem confirmacao de negocio

## Testes de Negocio Necessarios

- contato novo nao deve virar pedido
- entrega sem endereco nao deve virar pedido confirmado
- pedido so entra no board operacional apos confirmacao final
- atendimento ativo sem pedido deve aparecer apenas na area de atendimento
- handoff humano nao deve criar pedido

## Proximo Passo

Implementacao inicial recomendada:

1. corrigir o save precoce do fluxo legado de entrega
2. adicionar testes cobrindo essa regra
3. depois disso, introduzir a camada de `rascunho/processo`

