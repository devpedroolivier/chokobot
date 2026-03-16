# Contrato do Runtime de IA

## Objetivo
Definir os pontos estaveis do runtime de IA para execucao local, testes e futura evolucao do agente sem acoplamento ao ambiente.

## Componentes principais
- `app.ai.runner.build_ai_client()`: cria o cliente OpenAI apenas quando houver dependencia instalada e `OPENAI_API_KEY` valido.
- `app.ai.runner.get_ai_client()`: faz cache lazy do cliente para uso no runtime.
- `app.ai.runner.set_ai_client()` e `reset_ai_client()`: permitem controle explicito do cliente em testes.
- `app.ai.runner.AIRuntime`: agrupa as tools externas usadas pelo agente e permite injecao de dependencias.

## Garantias
- Importar `app.ai.runner` nao deve exigir segredo real.
- `process_message_with_ai()` aceita `ai_client` e `runtime` injetados para testes.
- O prompt de sistema e reconstruido a partir de `agent.instructions`, contexto temporal e learnings disponiveis no runtime.
- Chamadas de tool passam pelo roteador interno `handle_tool_call()` antes de voltarem ao loop da IA.

## Contrato das tools
- `get_menu(category) -> str`
- `get_learnings() -> str`
- `save_learning(aprendizado) -> str`
- `escalate_to_human(telefone, motivo) -> Any`
- `create_cake_order(telefone, nome_cliente, cliente_id, order) -> str`
- `create_sweet_order(telefone, nome_cliente, cliente_id, order) -> str`

## Regras de teste
- Testes unitarios devem preferir `ai_client` fake e `AIRuntime` injetado.
- Testes de fluxo nao devem depender de rede nem de segredo real.
- Cenarios exploratorios com API real permanecem fora da suite principal.
