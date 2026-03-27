# Documentação das Alterações — Plano de Ação da Auditoria

Data: 2026-03-27
Base: `PLANO_ACAO_AUDITORIA.md`

## 1) Runtime e políticas (anti-alucinação, contexto e Páscoa)

### Implementado
- Tratamento global de mensagem sem texto (mídia): resposta determinística sem escalar.
- Roteamento determinístico de foto/cardápio por contexto (bolos/presentes, doces, cafeteria, Páscoa).
- Contexto sazonal de Páscoa preservado/liberado conforme continuidade da conversa.
- Melhoria no detector de pedidos de catálogo/foto para evitar interceptações indevidas.
- Novo detector `mentions_easter` e reforço de `message_has_easter_context`.
- Novo detector `requests_knowledge_topic` com guardas para não roubar fluxo de pedido.

### Arquivos
- `app/ai/runner.py`
- `app/ai/policies.py`

## 2) Tools (validação forte, normalização e confiabilidade operacional)

### Implementado
- Normalização de massa:
  - `preta`, `massa preta`, `escura`, `massa escura` -> `Chocolate`.
- Validação obrigatória de pedidos:
  - `create_cake_order`, `create_sweet_order`, `create_gift_order` e cafeteria com pagamento obrigatório e total > 0.
  - Reforço de endereço obrigatório quando `modo_recebimento = entrega`.
- Reforço de validação de quantidade para doces (>0).
- Normalização do combo:
  - aliases para `combo relâmpago/combo do dia/choko combo/promoção de terça`.
  - rótulo canônico de exibição e persistência: `Choko Combo (Combo do Dia)`.
- Escalação com motivo mais robusto:
  - sanitização/enriquecimento para motivos genéricos/curtos.
- Resumo padronizado de rascunho:
  - Data/Horário, Retirada/Entrega, Pagamento, Kit Festou, subtotal/taxa quando aplicável.
- Retorno das tools de fechamento inclui flag textual de Kit Festou (`sim/nao`) para suportar regra pós-pedido.

### Arquivos
- `app/ai/tools.py`

## 3) Prompts dos agentes (regras de negócio e anti-erro)

### Implementado
- Regra obrigatória de PIX (sem placeholder e sem recusa) em agentes de atendimento/pedido.
- Triage com reforço anti-escalação para termos internos e regra de cardápio contextual.
- Cake:
  - anti-dedução explícita;
  - sinônimos de massa;
  - resumo obrigatório padronizado;
  - regra de oferta pós-pedido de Kit Festou (controlada).
- Sweet/Gift/Cafeteria:
  - resumo padronizado;
  - alinhamento de Páscoa para link único;
  - reforços de Kit Festou por contexto.
- Cafeteria:
  - combo de terça ajustado para `Choko Combo (Combo do Dia)`.

### Arquivo
- `app/ai/agents.py`

## 4) Startup/configuração

### Implementado
- Warning no startup quando `PIX_KEY` estiver ausente.

### Arquivo
- `app/application/use_cases/bootstrap_runtime.py`

## 5) Testes e regressão

### Atualizados/Adicionados
- Ajustes de prompt/regra para novo comportamento (`Choko Combo`, resumo padronizado, pagamento no resumo).
- Novos testes para:
  - normalização de massa preta;
  - rejeição de dados incompletos;
  - rejeição de total zero;
  - enriquecimento de motivo de escalação;
  - warning de startup sem PIX.
- Ajustes de testes de catálogo contextual por tipo (ex.: foto de doces -> link de doces).

### Arquivos
- `tests/test_ai_agent_prompts.py`
- `tests/test_ai_cafeteria_order.py`
- `tests/test_sprint5_regression.py`
- `tests/test_delivery_and_line_rules.py`
- `tests/test_app_bootstrap.py`
- `tests/test_message_formatting.py`

## 6) Validação final

Comando executado:
- `python3 -m unittest discover -s tests`

Resultado:
- **297 testes executados, todos passando**.
