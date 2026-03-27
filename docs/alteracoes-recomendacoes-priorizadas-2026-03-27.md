# Alterações Aplicadas — Recomendações Objetivas e Priorizadas (2026-03-27)

## Objetivo
Aplicar correções estruturais para reduzir reincidência de erros da IA em:
- anti-alucinação operacional (PIX, taxa, confirmação, catálogo)
- manutenção de contexto (especialmente Páscoa versus mudança de assunto)
- precisão temporal (disponibilidade por dia e exceções operacionais)
- robustez de execução (falhas de tabela/infra)

## Mudanças Implementadas

### 1) Guardrail determinístico para PIX
- Adicionado detector explícito de pedido de chave PIX em `policies`.
- Criada resposta determinística em `runner` para chave PIX (sem depender do modelo).
- Ao usar pagamento PIX nos resumos de pedido, a linha de pagamento agora inclui a chave PIX oficial quando configurada.
- Adicionada resposta determinística para pergunta de taxa/frete:
  - bolos/encomendas/presentes = R$10,00
  - cafeteria = R$5,00

Arquivos:
- `app/ai/policies.py`
- `app/ai/runner.py`
- `app/ai/tools.py`

Impacto esperado:
- evita omissão de PIX quando o cliente pede chave
- reduz handoff indevido por “não consegui informar PIX”

### 2) Contexto de Páscoa baseado em continuidade real (não palavra isolada)
- Criada função de contexto de Páscoa mais robusta (`message_has_easter_context`) para reduzir falso positivo por palavra isolada.
- Fluxo agora libera contexto de Páscoa imediatamente quando o cliente muda de assunto, inclusive antes de interceptores como PIX/pós-venda.
- Mantido o comportamento: pedir apenas cardápio de Páscoa envia link sem handoff imediato; continuidade no mesmo tema direciona para humano.

Arquivos:
- `app/ai/policies.py`
- `app/ai/runner.py`
- `app/ai/agents.py` (ajuste de regra no prompt de Knowledge)

Impacto esperado:
- menos handoff indevido
- melhor aderência ao “contexto vigente da interação”

### 3) Precisão temporal e disponibilidade do Combo Relâmpago
- Implementada validação determinística de disponibilidade por dia para itens da cafeteria com restrição semanal.
- `Combo Relampago` agora bloqueia fechamento fora de terça-feira e informa a data solicitada.
- Adicionada inferência de variante do combo por alias (ex.: “combo suco”, “combo refri”).

Arquivos:
- `app/ai/tools.py`

Impacto esperado:
- evita fechamento incoerente fora da regra comercial da promoção
- melhora acerto de soma/variante do combo na operação real

### 4) Transparência de taxa de entrega no resumo
- Resumos de rascunho (bolo/doces/presentes) agora exibem linha de taxa de entrega quando aplicável.
- Resposta final de pedido de presente também exibe taxa quando houver.

Arquivo:
- `app/ai/tools.py`

Impacto esperado:
- reduz casos de “não cobrou taxa de entrega” por falta de visibilidade no resumo

### 5) Robustez de repositório (erro `no such table: clientes`)
- `get_customer_by_phone` agora retorna `None` quando a tabela `clientes` não existe, evitando quebra de fluxo de saudação/known-customer.

Arquivo:
- `app/infrastructure/repositories/sqlite_customer_repository.py`

Impacto esperado:
- evita erro operacional em ambientes de teste/inicialização parcial de banco

## Testes de Regressão Adicionados/Ajustados

Novos testes:
- PIX determinístico e liberação de contexto de Páscoa:
  - `tests/test_ai_runtime_bootstrap.py`
- Detecção de chave PIX e contexto de Páscoa:
  - `tests/test_ai_policies.py`
- Combo Relâmpago:
  - bloqueio fora de terça
  - inferência por alias no nome
  - `tests/test_ai_cafeteria_order.py`
- Resiliência quando `clientes` não existe:
  - `tests/test_customer_repository.py`
- Formatação com chave PIX no resumo:
  - `tests/test_message_formatting.py`
- Prompt de Knowledge alinhado com regra de handoff por contexto:
  - `tests/test_ai_agent_prompts.py`

Ajuste de teste existente:
- `tests/test_ai_cafeteria_order.py`: data do cenário de combo movida para terça-feira (24/03/2026).

## Validação Executada
- `python3 -m unittest tests.test_ai_policies tests.test_ai_runtime_bootstrap tests.test_ai_cafeteria_order tests.test_message_formatting tests.test_customer_repository tests.test_ai_agent_prompts`
- `python3 -m unittest tests.test_ai_easter_flow tests.test_ai_tool_execution tests.test_ai_time_rule tests.test_ai_payment_rules tests.test_operational_calendar tests.test_ai_runtime_bootstrap`
- `python3 -m compileall app tests`

Status: todos os comandos acima concluídos com sucesso.
