# PLANO DE AÇÃO — AUDITORIA DE ATENDIMENTO CHOKOBOT

> Plano executável baseado na auditoria completa de conversas reais.
> Cada item contém: problema, impacto, arquivos envolvidos, ação técnica e critério de aceite.

---

## FASE 1 — CORREÇÕES CRÍTICAS (impacto direto em perda de venda)

### 1.1. Chave PIX inconsistente / placeholder vazado

**Problema:** O bot apresenta 3 comportamentos diferentes quando o cliente pede a chave PIX:
- Recusa: "Não posso fornecer a chave PIX"
- Placeholder: "[insira a chave aqui]" enviado ao cliente
- Correto: Chave real enviada

**Impacto:** Cliente não consegue pagar → abandono do pedido. 3 ocorrências reais de placeholder enviado.

**Causa raiz:** O `_pix_key_reply()` no `runner.py` funciona corretamente, mas os agentes (CakeOrderAgent, GiftOrderAgent, SweetOrderAgent) têm a chave PIX via `_PIX_INFO_LINE` no prompt — quando o LLM decide responder sem usar a função `_pix_key_reply()`, ele pode inventar ou usar placeholder.

**Arquivos:**
- `app/ai/runner.py` — linhas 120-130: `_pix_key_reply()` (já correto)
- `app/ai/agents.py` — linhas 30-32: `_PIX_INFO_LINE` (variável injetada no prompt)
- `app/settings.py` — linha 69/135: `pix_key` no settings
- `.env` / `.env.example` — `PIX_KEY`

**Ação técnica:**
1. Verificar que `PIX_KEY` está definida no `.env` de produção com valor real
2. No `app/ai/agents.py`, reforçar a instrução em TODOS os prompts dos agentes de pedido (CAKE_ORDER_PROMPT, SWEET_ORDER_PROMPT, GIFT_ORDER_PROMPT, CAFETERIA_PROMPT):
   ```
   REGRA DE PIX — OBRIGATÓRIA:
   Quando o cliente pedir chave PIX ou forma de pagamento PIX, responda EXATAMENTE com:
   "{_PIX_INFO_LINE}"
   NUNCA use placeholders como "[insira a chave aqui]". NUNCA recuse fornecer a chave PIX.
   ```
3. Adicionar validação no startup (`app/main.py` ou `app/settings.py`) que loga warning se `PIX_KEY` estiver vazia
4. Garantir que o `_requests_pix_key_info` no runner intercepte TODAS as variações de pedido de PIX antes de chegar no LLM

**Critério de aceite:**
- [ ] `PIX_KEY` está configurada no `.env` de produção
- [ ] Teste: enviar "me passa a chave pix" → resposta contém a chave real (nunca placeholder)
- [ ] Teste: enviar "qual o pix?" → resposta contém a chave real
- [ ] Startup loga warning se `PIX_KEY` está vazia
- [ ] Nenhum prompt de agente contém placeholder ou instrução ambígua sobre PIX

---

### 1.2. Encomendas salvas sem dados obrigatórios

**Problema:** 57 de 109 encomendas tradicionais estão sem massa, recheio ou mousse. 16 encomendas têm valor R$0,00.

**Impacto:** Pedidos incompletos exigem retrabalho manual da equipe, risco de erro na produção.

**Causa raiz:** A tool `create_cake_order` não valida campos obrigatórios antes de salvar no banco.

**Arquivos:**
- `app/ai/tools.py` — linhas 59-60 (constantes), ~1700+ (`create_cake_order`)
- `app/ai/agents.py` — linhas 297-316 (fluxo de confirmação)

**Ação técnica:**
1. Na função `create_cake_order` em `app/ai/tools.py`, adicionar validação ANTES de gravar:
   - Para categoria `tradicional`: exigir `massa`, `recheio`, `tamanho`, `data_entrega`, `modo_recebimento`, `pagamento`
   - Exceção: recheio `Casadinho` não exige mousse
   - Para categoria `ingles`, `redondo`, `torta`: exigir `produto`, `data_entrega`, `modo_recebimento`, `pagamento`
   - Para TODAS as categorias: exigir `valor_total > 0`
   - Se algum campo obrigatório estiver faltando, retornar mensagem de erro para o LLM com os campos pendentes (NÃO salvar)
2. Adicionar a mesma validação em `create_sweet_order` e `create_gift_order`
3. Se `modo_recebimento == "entrega"`, exigir que `endereco` não esteja vazio

**Critério de aceite:**
- [ ] Teste: chamar `create_cake_order` com massa vazia para tradicional → rejeita com lista de campos faltantes
- [ ] Teste: chamar `create_cake_order` com valor_total=0 → rejeita
- [ ] Teste: chamar `create_cake_order` com entrega sem endereço → rejeita
- [ ] Teste: pedido completo → salva normalmente
- [ ] Testes unitários cobrindo as validações

---

### 1.3. Escalações indevidas — itens dentro do escopo

**Problema:** 31+ escalações para humano de itens que têm agente dedicado:
- "Cesta de café da manhã" → escalada (deveria ir a GiftOrderAgent)
- "Suco de laranja" → escalada (deveria ir a CafeteriaAgent)
- "Bombons e brigadeiros" → escalada (deveria ir a SweetOrderAgent)
- "Cheesecake baixa" → escalada (produto que EXISTE no cardápio de tortas)

**Impacto:** Sobrecarga da equipe, perda de venda automatizável, experiência fragmentada.

**Causa raiz:** O TriageAgent usa `escalate_to_human` com motivos genéricos ("fora de contexto", "não está no escopo") em vez de `transfer_to_agent`.

**Arquivos:**
- `app/ai/agents.py` — linhas 50-132 (TRIAGE_PROMPT)
- `app/ai/agents.py` — linhas 477-545 (GIFT_ORDER_PROMPT — cestas personalizadas)
- `app/ai/policies.py` — detecção de intenções

**Ação técnica:**
1. No `TRIAGE_PROMPT`, reforçar a regra anti-escalação com exemplos concretos:
   ```
   ⚠️ LISTA DE TERMOS QUE NUNCA DEVEM SER ESCALADOS:
   - "cesta", "cesta de café", "cesta personalizada", "presente" → GiftOrderAgent
   - "brigadeiro", "bombom", "docinhos", "docinho", "camafeu" → SweetOrderAgent
   - "croissant", "café", "cappuccino", "suco", "salgado", "fatia" → CafeteriaAgent
   - "cheesecake", "torta", "bolo simples", "caseirinho" → CakeOrderAgent
   - "preço", "valor", "quanto custa", "cardápio" → KnowledgeAgent
   ```
2. No `TRIAGE_PROMPT`, adicionar regra negativa explícita:
   ```
   ❌ NUNCA use escalate_to_human para os termos acima. SEMPRE use transfer_to_agent.
   escalate_to_human é SOMENTE para: currículo, outro restaurante, pedido de emprego,
   assunto 100% alheio à confeitaria.
   ```
3. Considerar adicionar detecção determinística no `policies.py` que force roteamento antes do LLM decidir (similar ao `requests_human_handoff`)

**Critério de aceite:**
- [ ] Teste: "quero uma cesta de café da manhã" → transferido para GiftOrderAgent (NÃO escalado)
- [ ] Teste: "tem brigadeiro?" → transferido para SweetOrderAgent ou KnowledgeAgent
- [ ] Teste: "quero suco de laranja" → transferido para CafeteriaAgent
- [ ] Teste: "quero enviar currículo" → escalado para humano (correto)
- [ ] Zero escalações indevidas para produtos internos nos testes de regressão

---

## FASE 2 — VIOLAÇÕES DE REGRAS DE NEGÓCIO

### 2.1. "Massa preta" não normalizada para "Chocolate"

**Problema:** Quando o cliente diz "massa preta", o bot tem 2 comportamentos:
- Suzana (24/03): Entendeu como Chocolate (correto)
- Talita (27/03): "A massa preta não está disponível" (incorreto)

**Impacto:** Cliente rejeitado por usar vocabulário popular. "Massa preta" é como clientes reais falam.

**Arquivos:**
- `app/ai/tools.py` — linhas 59-60 (`MASSAS_TRADICIONAIS`, `MASSAS_VALIDAS`)
- `app/ai/tools.py` — ~linha 1330 (`_match_closest` para massa)
- `app/ai/agents.py` — CAKE_ORDER_PROMPT (instruções do agente)

**Ação técnica:**
1. Em `app/ai/tools.py`, criar dicionário de sinônimos ANTES da validação:
   ```python
   MASSA_SINONIMOS = {
       "preta": "Chocolate",
       "massa preta": "Chocolate",
       "escura": "Chocolate",
       "massa escura": "Chocolate",
   }
   ```
2. Na função `_match_closest` ou antes de chamar a validação de massa, normalizar:
   ```python
   def _normalizar_massa(massa_raw: str) -> str:
       key = massa_raw.strip().casefold()
       return MASSA_SINONIMOS.get(key, massa_raw)
   ```
3. No `CAKE_ORDER_PROMPT`, adicionar instrução explícita:
   ```
   SINÔNIMOS DE MASSA:
   - "massa preta" ou "preta" = Chocolate
   - "massa escura" ou "escura" = Chocolate
   Quando o cliente usar esses termos, interprete como Chocolate sem perguntar.
   ```

**Critério de aceite:**
- [ ] Teste: "quero massa preta" → tratado como Chocolate automaticamente
- [ ] Teste: "massa escura" → tratado como Chocolate
- [ ] Teste: `_normalizar_massa("preta")` retorna "Chocolate"
- [ ] Encomenda salva com massa="Chocolate" (não "preta" ou "massa preta")

---

### 2.2. "Combo Relâmpago" não normalizado para "Choko Combo"

**Problema:** O bot usa "Combo Relâmpago" literalmente. A regra exige que seja tratado como "Choko Combo (Combo do Dia)".

**Impacto:** Inconsistência de nomenclatura entre canais, possível confusão na cozinha.

**Arquivos:**
- `app/ai/agents.py` — linhas 587-589 (CAFETERIA_PROMPT, referência ao Combo Relâmpago)
- `app/ai/tools.py` — `create_cafeteria_order` (onde o item é registrado)

**Ação técnica:**
1. No `CAFETERIA_PROMPT` (linhas 587-589), substituir:
   ```
   DE: "Combo Relampago"
   PARA: "Choko Combo (Combo do Dia)"
   ```
   Manter a regra de terça-feira e composição (1 Croissant + 1 Bolo Gelado + 1 Bebida por R$23,99).
2. Adicionar sinônimo no prompt:
   ```
   Se o cliente disser "combo relâmpago", "combo do dia", "promoção de terça" ou "choko combo",
   trate como "Choko Combo (Combo do Dia)".
   ```
3. Se houver normalização no `create_cafeteria_order`, garantir que o item seja registrado como "Choko Combo".

**Critério de aceite:**
- [ ] Teste: "quero o combo relâmpago" → bot responde com "Choko Combo (Combo do Dia)"
- [ ] Teste: pedido registrado com nome "Choko Combo" (não "Combo Relâmpago")
- [ ] Prompt do CafeteriaAgent não contém mais "Combo Relâmpago" como nome principal

---

### 2.3. Kit Festou não ofertado após finalização do pedido

**Problema:** A regra exige que o Kit Festou seja oferecido APÓS a finalização da encomenda, bolo pronto ou pedido entregue. Atualmente é oferecido apenas DURANTE o pedido como upsell. Apenas 23 de 145 pedidos (15,8%) incluem Kit Festou.

**Impacto:** Perda de oportunidade de upsell em 84% dos pedidos.

**Arquivos:**
- `app/ai/agents.py` — linhas 187-190 (regra de upsell no CAKE_ORDER_PROMPT)
- `app/ai/agents.py` — linhas 597-600 (regra de Kit Festou no CAFETERIA_PROMPT)
- `app/ai/tools.py` — `create_cake_order`, `create_cafeteria_order` (pós-salvamento)

**Ação técnica:**
1. Nos prompts de CAKE_ORDER_PROMPT, SWEET_ORDER_PROMPT e CAFETERIA_PROMPT, adicionar regra pós-confirmação:
   ```
   REGRA DE KIT FESTOU PÓS-PEDIDO (OBRIGATÓRIA):
   Após salvar o pedido com sucesso (create_cake_order/create_sweet_order/create_cafeteria_order),
   SE o pedido NÃO incluir Kit Festou, ofereça UMA VEZ:
   "Aproveite e adicione o Kit Festou por apenas R$35,00! Inclui 25 brigadeiros + 1 balão personalizado. Quer adicionar?"
   Se o cliente aceitar, atualize o pedido. Se recusar, agradeça e finalize.
   ```
2. Nas funções `create_*_order`, incluir no retorno de sucesso um flag indicando se Kit Festou já foi incluído, para que o agente saiba se deve ofertar.
3. Manter a regra existente de NÃO ofertar Kit Festou para itens sem bolo (café, croissant avulso, doces).

**Critério de aceite:**
- [ ] Teste: pedido de bolo sem Kit Festou → após confirmação, bot oferece Kit Festou
- [ ] Teste: pedido de bolo COM Kit Festou → não repete oferta
- [ ] Teste: pedido de croissant avulso → NÃO oferece Kit Festou
- [ ] Teste: cliente recusa Kit Festou → bot finaliza sem insistir

---

### 2.4. Dedução indevida de informações do pedido

**Problema:** O bot às vezes interpreta dados sem confirmar com o cliente.
- Suzana pediu "recheio de leite ninho" → bot converteu para "Doce de Leite" sem confirmar
- Casos onde mousse é confundido com recheio

**Impacto:** Pedido pode ser produzido com especificações erradas.

**Arquivos:**
- `app/ai/agents.py` — linhas 159-178 (REGRA 2 — MOUSSE NÃO É RECHEIO)
- `app/ai/agents.py` — linhas 296-316 (fluxo de confirmação)

**Ação técnica:**
1. No CAKE_ORDER_PROMPT, adicionar regra de anti-dedução:
   ```
   REGRA DE ANTI-DEDUÇÃO (OBRIGATÓRIA):
   NUNCA assuma, deduza ou converta informações do pedido sem confirmação explícita do cliente.
   Se o cliente disser algo ambíguo como "recheio de leite ninho":
   - NÃO assuma que é "Doce de Leite" ou "Brigadeiro Branco de Ninho"
   - PERGUNTE: "Você quer dizer o recheio Doce de Leite ou Brigadeiro Branco de Ninho?"
   Se houver qualquer dúvida entre recheio e mousse, PERGUNTE antes de registrar.
   ```
2. No fluxo de confirmação (linhas 296-316), adicionar instrução para que o resumo mostre EXATAMENTE o que o cliente disse (entre parênteses) + a interpretação do bot, para validação visual:
   ```
   No resumo, se houve qualquer interpretação/conversão, destaque:
   "Recheio: Doce de Leite (você disse 'leite ninho' — correto?)"
   ```

**Critério de aceite:**
- [ ] Teste: "recheio de leite ninho" → bot pergunta para esclarecer, não assume
- [ ] Teste: "ninho com brigadeiro" → bot registra recheio=Brigadeiro, mousse=Ninho (conforme regra 2)
- [ ] Teste: resumo final mostra todos os campos de forma explícita para confirmação

---

### 2.5. Links de cardápio não enviados ao pedir foto/cardápio

**Problema:** Quando cliente pede foto ou cardápio, o bot às vezes escala para humano em vez de enviar o link do catálogo visual. A regra `_PHOTO_RULE_LINE` existe mas não é aplicada consistentemente.

**Impacto:** Escalação desnecessária, perda de venda automática.

**Arquivos:**
- `app/ai/agents.py` — todas as `_PHOTO_RULE_LINE` (linhas 33-36, 141, 325, 411, 484, 554)
- `app/ai/runner.py` — linhas 106-117 (`_catalog_photo_reply`)
- `app/settings.py` — linhas 66-68 (URLs dos catálogos)

**Ação técnica:**
1. No `runner.py`, adicionar detecção determinística para pedidos de foto/cardápio ANTES do LLM processar (similar ao `_requests_pix_key_info`):
   ```python
   def _requests_photo_or_catalog(text: str) -> bool:
       normalized = (text or "").casefold()
       return bool(re.search(
           r"\b(foto|fotos|imagem|imagens|ver|visualizar|catálogo|catalogo|cardápio|cardapio|menu)\b",
           normalized
       ))
   ```
2. Garantir que a resposta inclua o link CORRETO conforme o contexto:
   - Contexto bolo/encomenda → `CATALOG_LINK` (presenteschoko)
   - Contexto cafeteria → `CAFETERIA_URL` (bit.ly/44ZlKlZ)
   - Contexto doces → `DOCES_URL` (bit.ly/doceschoko)
   - Contexto Páscoa → `pascoachoko.goomer.app`
3. No TRIAGE_PROMPT, adicionar regra de cardápio contextual:
   ```
   REGRA DE CARDÁPIO/LINK:
   Se o cliente pedir "cardápio", "menu", "foto", "opções":
   - Identifique o contexto da conversa (bolo, cafeteria, doces, presentes, Páscoa)
   - Envie o link correspondente ao contexto
   - Se o contexto for ambíguo, pergunte sobre qual categoria antes de enviar link
   NUNCA escale para humano um pedido de cardápio.
   ```

**Critério de aceite:**
- [ ] Teste: "me manda o cardápio de bolos" → link do catálogo enviado (não escalação)
- [ ] Teste: "tem foto dos docinhos?" → link do catálogo de doces enviado
- [ ] Teste: "cardápio de Páscoa" → link pascoachoko.goomer.app
- [ ] Teste: "quero ver as opções da cafeteria" → link da cafeteria

---

## FASE 3 — PROBLEMAS DE EXPERIÊNCIA DO CLIENTE

### 3.1. Respostas duplicadas por mensagens rápidas

**Problema:** Quando o cliente envia 3+ mensagens rápidas (comportamento natural no WhatsApp), o bot processa cada uma isoladamente e responde com a welcome message repetida. Casos reais:
- Eduarda: recebeu welcome 4x seguidas
- Rafa Bertone: recebeu welcome 3x ignorando suas perguntas
- Erica Novais: recebeu welcome 2x

**Impacto:** Cliente sente que não é ouvido, experiência frustrante, possível abandono.

**Arquivos:**
- `app/api/routes/webhook.py` — linhas 120-123 (deduplicação existente por message_id)
- `app/security.py` — linhas 151-165 (replay detection)
- `app/ai/runner.py` — processamento de mensagem

**Ação técnica:**
1. Implementar debounce por telefone no webhook handler:
   ```python
   # Ao receber mensagem, em vez de processar imediatamente:
   # 1. Armazenar a mensagem num buffer por telefone
   # 2. Aguardar 3 segundos para agregar mensagens subsequentes do mesmo telefone
   # 3. Concatenar todas as mensagens no buffer e processar como uma única
   ```
2. Alternativa mais simples: Adicionar um lock por telefone que impede processamento paralelo:
   ```python
   _phone_locks: dict[str, asyncio.Lock] = {}

   async def process_with_lock(phone, message):
       lock = _phone_locks.setdefault(phone, asyncio.Lock())
       async with lock:
           # processa mensagem
           # mensagens que chegaram enquanto o lock estava ativo são processadas em sequência
   ```
3. No runner, ao detectar que já existe uma resposta recente (< 3s) para o mesmo telefone, agregar o contexto em vez de reenviar welcome.

**Critério de aceite:**
- [ ] Teste: enviar 3 mensagens rápidas ("Oi", "Tudo bem?", "Quero um bolo") → bot responde UMA vez com contexto completo
- [ ] Teste: enviar mensagens com 30s de intervalo → bot responde cada uma normalmente
- [ ] Sem respostas duplicadas de welcome message

---

### 3.2. Pergunta binária proibida na abertura

**Problema:** A regra diz "NUNCA comece com a pergunta binária 'pronta entrega ou encomenda?'". Porém, o welcome message antigo estava overriding essa regra. 23 ocorrências reais dessa pergunta binária.

**Impacto:** Ignora o contexto que o cliente já trouxe, gera atrito.

**Nota:** O `WELCOME_MESSAGE` atual em `app/welcome_message.py` JÁ está correto (não faz pergunta binária). O problema ocorria com a versão anterior. Verificar se o deploy atual está usando a versão correta.

**Arquivos:**
- `app/welcome_message.py` — linhas 1-11 (versão atual está OK)
- `app/ai/agents.py` — linhas 56-59 (regra de saudação no TRIAGE_PROMPT)

**Ação técnica:**
1. Verificar que o deploy de produção está com a versão atualizada do `WELCOME_MESSAGE`
2. No TRIAGE_PROMPT, reforçar a regra anti-binária com exemplo negativo:
   ```
   ❌ PROIBIDO: "Pronta Entrega ou Encomendas personalizadas?"
   ❌ PROIBIDO: qualquer variação de pergunta binária na abertura
   ✅ CORRETO: usar o WELCOME_MESSAGE definido e aguardar o cliente indicar o que quer
   ```
3. Adicionar teste de regressão que valida que a resposta de saudação NÃO contém "Pronta Entrega.*Encomendas"

**Critério de aceite:**
- [ ] Teste: enviar "Oi" → resposta NÃO contém pergunta binária pronta entrega/encomenda
- [ ] Teste: enviar "Bom dia, quero um bolo" → bot roteia para CakeOrderAgent (sem perguntar binário)
- [ ] Deploy de produção usa WELCOME_MESSAGE atualizado
- [ ] Teste de regressão automatizado

---

### 3.3. Páscoa — comportamento inconsistente

**Problema:** O tratamento de Páscoa tem 3 comportamentos diferentes:
1. Envia link `pascoachoko.goomer.app` corretamente (88 ocorrências)
2. Escala para humano (4 ocorrências: "ovos pronta entrega exigem atendimento humano")
3. Diz "não temos essa opção" (pelo menos 1 caso com "ovo de Páscoa")

**Impacto:** Confusão do cliente, possível perda de venda de Páscoa.

**Arquivos:**
- `app/ai/agents.py` — linhas 104-108 (regra de Páscoa no TRIAGE_PROMPT)
- `app/ai/agents.py` — linhas 424-430 (regra de Páscoa no KNOWLEDGE_PROMPT)
- `app/ai/agents.py` — linhas 488-489 (regra de Páscoa no GIFT_ORDER_PROMPT)
- `app/ai/agents.py` — linhas 569-571 (regra de Páscoa no CAFETERIA_PROMPT)
- `app/ai/policies.py` — detecção de intenção de Páscoa

**Ação técnica:**
1. Adicionar detecção determinística de intenção de Páscoa no `policies.py`:
   ```python
   def mentions_easter(text: str) -> bool:
       normalized = (text or "").casefold()
       return bool(re.search(
           r"\b(p[aá]scoa|ovo|ovos|trio|tablete|mini.?ovo|mimos.?p[aá]scoa)\b",
           normalized
       ))
   ```
2. No `runner.py`, interceptar ANTES do LLM:
   ```python
   if mentions_easter(text):
       return EASTER_CATALOG_MESSAGE  # Resposta determinística
   ```
3. Remover a regra de escalação "ovos pronta entrega exigem atendimento humano" e substituir pela regra universal de link.
4. Garantir que TODOS os agentes tenham a mesma resposta determinística para Páscoa.

**Critério de aceite:**
- [ ] Teste: "quero ovo de Páscoa" → link pascoachoko.goomer.app (não escalação, não "não temos")
- [ ] Teste: "ovos pronta entrega" → link pascoachoko.goomer.app
- [ ] Teste: "cardápio de Páscoa" → link pascoachoko.goomer.app
- [ ] 100% de consistência nas respostas de Páscoa

---

## FASE 4 — OTIMIZAÇÕES DE FLUXO

### 4.1. Número de teste poluindo dados de produção

**Problema:** O número `5511888888888` gerou 80+ escalações entre 23/03 e 27/03, todas com motivo "cliente pediu ajuda". Polui métricas e logs.

**Arquivos:**
- `app/api/routes/webhook.py` — handler de webhook
- `app/settings.py` — configurações

**Ação técnica:**
1. Adicionar variável de ambiente `TEST_PHONES` com lista de telefones de teste
2. No webhook handler, se o telefone estiver na lista de teste E o ambiente for produção, ignorar ou marcar como teste
3. No arquivo `atendimentos.txt`, filtrar por telefones de teste nos relatórios
4. Alternativa: criar flag `is_test` nos registros do banco

**Critério de aceite:**
- [ ] Mensagens de telefones de teste não geram escalações no log de produção
- [ ] Métricas de escalação refletem apenas clientes reais
- [ ] Telefones de teste configuráveis via `.env`

---

### 4.2. Melhoria nas mensagens de escalação

**Problema:** 12 escalações com motivo vago "Cliente mencionou algo que não está claro" e 19 com motivo genérico "fora de contexto". Isso dificulta o atendente humano entender o que o cliente precisa.

**Arquivos:**
- `app/ai/tools.py` — `escalate_to_human` (parâmetro `motivo`)
- `app/ai/agents.py` — instruções de escalação

**Ação técnica:**
1. Em TODOS os prompts de agentes, instruir que o motivo da escalação deve ser DESCRITIVO:
   ```
   Ao usar escalate_to_human, o campo "motivo" deve conter:
   1. O que o cliente pediu (produto/serviço específico)
   2. Por que você não pôde atender (fora do catálogo, precisa de confirmação da equipe, etc.)
   Exemplo bom: "Cliente quer cesta personalizada com frutas e vinho. Produto fora do catálogo padrão."
   Exemplo ruim: "Cliente mencionou algo que não está claro."
   ```
2. Na tool `escalate_to_human`, adicionar validação mínima do motivo (mínimo 20 caracteres, não pode ser genérico)

**Critério de aceite:**
- [ ] Teste: escalação contém motivo descritivo (não genérico)
- [ ] Motivo tem no mínimo 20 caracteres
- [ ] Motivo não contém frases genéricas como "não está claro", "fora de contexto" sem especificar o produto

---

### 4.3. Confirmação de dados completa antes da finalização

**Problema:** O resumo final antes da confirmação nem sempre mostra todos os campos obrigatórios. Casos onde o pagamento não é confirmado, ou modo de recebimento fica implícito.

**Arquivos:**
- `app/ai/agents.py` — linhas 296-316 (fluxo de confirmação do CAKE_ORDER_PROMPT)
- `app/ai/agents.py` — linhas 389-400 (fluxo do SWEET_ORDER_PROMPT)
- `app/ai/agents.py` — linhas 522-530 (fluxo do GIFT_ORDER_PROMPT)
- `app/ai/agents.py` — linhas 620-628 (fluxo do CAFETERIA_PROMPT)

**Ação técnica:**
1. Padronizar o formato de resumo em TODOS os agentes de pedido:
   ```
   FORMATO OBRIGATÓRIO DO RESUMO (todos os campos devem aparecer):
   "Confirma seu pedido?
   📦 [produto] x[quantidade] — [detalhes: massa, recheio, mousse, adicional]
   📅 Data: [DD/MM/AAAA] | Horário: [HH:MM]
   🚗 [Retirada na loja / Entrega: endereço completo]
   💰 Total: R$[valor] (+ R$10 entrega se aplicável)
   💳 Pagamento: [PIX / Cartão / Dinheiro]
   🎁 Kit Festou: [Sim (+R$35) / Não incluso]"
   ```
2. Adicionar instrução de que TODOS os campos são obrigatórios no resumo. Se algum estiver faltando, perguntar ANTES de montar o resumo.
3. No resumo, se entrega: mostrar endereço completo + taxa. Se retirada: mostrar "Retirada na loja".

**Critério de aceite:**
- [ ] Teste: resumo final contém TODOS os campos obrigatórios
- [ ] Teste: resumo de entrega mostra endereço + taxa R$10
- [ ] Teste: resumo de retirada mostra "Retirada na loja"
- [ ] Formato idêntico em todos os agentes de pedido

---

### 4.4. Resposta para mensagens de mídia (foto, áudio, sticker)

**Problema:** Mensagens sem texto (imagens, áudios, stickers) às vezes causam comportamento inesperado ou escalação.

**Arquivos:**
- `app/ai/agents.py` — linhas 563-567 (regra de mídia no CAFETERIA_PROMPT)
- `app/ai/runner.py` — processamento de mensagem

**Ação técnica:**
1. No `runner.py`, detectar mensagens vazias (sem texto) ANTES de enviar ao LLM:
   ```python
   if not text or not text.strip():
       return "Recebi uma mídia, mas ainda não consigo visualizar fotos ou áudios aqui 😊\nPode me contar em texto o que você está procurando?"
   ```
2. Garantir que esta regra se aplica GLOBALMENTE, não apenas no CafeteriaAgent.

**Critério de aceite:**
- [ ] Teste: enviar mensagem sem texto → resposta padrão de mídia
- [ ] Teste: NÃO escala para humano ao receber mídia
- [ ] Resposta é consistente independente do agente ativo

---

## FASE 5 — TESTES DE REGRESSÃO

### 5.1. Testes automatizados para as regras de negócio

**Arquivos:**
- `tests/test_ai_policies.py` — testes de políticas
- `tests/test_ai_agent_prompts.py` — testes de prompts
- `tests/test_sprint5_regression.py` — testes de regressão

**Ação técnica:**
Adicionar os seguintes testes:

```python
# 1. Massa preta → Chocolate
def test_massa_preta_normalizada():
    assert _normalizar_massa("preta") == "Chocolate"
    assert _normalizar_massa("massa preta") == "Chocolate"
    assert _normalizar_massa("escura") == "Chocolate"

# 2. Combo Relâmpago → Choko Combo
def test_combo_relampago_normalizado():
    assert "Choko Combo" in CAFETERIA_PROMPT
    assert "Combo Relampago" not in CAFETERIA_PROMPT  # como nome principal

# 3. PIX key presente
def test_pix_key_configurada():
    settings = get_settings()
    assert settings.pix_key, "PIX_KEY deve estar configurada"

# 4. Welcome message sem pergunta binária
def test_welcome_sem_pergunta_binaria():
    assert "Pronta Entrega" not in WELCOME_MESSAGE or "Encomendas personalizadas" not in WELCOME_MESSAGE

# 5. Validação de encomenda completa
def test_create_cake_order_rejeita_dados_incompletos():
    # Testar que massa vazia é rejeitada para tradicional
    # Testar que valor_total=0 é rejeitado
    # Testar que entrega sem endereço é rejeitada

# 6. Kit Festou mencionado no pós-pedido
def test_kit_festou_pos_pedido():
    assert "Kit Festou" in CAKE_ORDER_PROMPT
    # Verificar que a instrução pós-pedido existe

# 7. Escalação não ocorre para produtos internos
def test_nao_escala_produtos_internos():
    # "cesta" não deve gerar escalação
    # "brigadeiro" não deve gerar escalação
    # "croissant" não deve gerar escalação
```

**Critério de aceite:**
- [ ] Todos os testes passam no CI
- [ ] Testes cobrem todas as 6 regras de negócio auditadas
- [ ] `python scripts/run_tests.py` passa sem falhas

---

## CHECKLIST GERAL DE EXECUÇÃO

### Fase 1 — Críticas
- [ ] 1.1 PIX: `.env` configurado + prompt reforçado + validação no startup
- [ ] 1.2 Dados obrigatórios: validação em `create_cake_order` + testes
- [ ] 1.3 Escalações indevidas: TRIAGE_PROMPT + exemplos negativos + testes

### Fase 2 — Regras de Negócio
- [ ] 2.1 "Massa preta": sinônimos + normalização + instrução no prompt
- [ ] 2.2 "Combo Relâmpago": renomear para "Choko Combo" no prompt
- [ ] 2.3 Kit Festou pós-pedido: regra em todos os agentes de pedido
- [ ] 2.4 Anti-dedução: regra de confirmação explícita + resumo detalhado
- [ ] 2.5 Links de cardápio: detecção determinística + link contextual

### Fase 3 — Experiência
- [ ] 3.1 Debounce: agregação de mensagens rápidas por telefone
- [ ] 3.2 Welcome message: verificar deploy + teste de regressão
- [ ] 3.3 Páscoa: detecção determinística + resposta única

### Fase 4 — Otimizações
- [ ] 4.1 Telefones de teste: filtro configurável
- [ ] 4.2 Motivos de escalação: mínimo 20 chars + descritivo
- [ ] 4.3 Resumo padronizado: formato único em todos os agentes
- [ ] 4.4 Mensagens de mídia: tratamento global

### Fase 5 — Testes
- [ ] 5.1 Testes de regressão: 7+ cenários cobrindo todas as regras

---

## REFERÊNCIA RÁPIDA — ARQUIVOS POR MUDANÇA

| Mudança | Arquivos |
|---------|----------|
| PIX | `app/ai/agents.py`, `app/ai/runner.py`, `app/settings.py`, `.env` |
| Dados obrigatórios | `app/ai/tools.py` |
| Escalações | `app/ai/agents.py` (TRIAGE_PROMPT), `app/ai/policies.py` |
| Massa preta | `app/ai/tools.py`, `app/ai/agents.py` (CAKE_ORDER_PROMPT) |
| Combo Relâmpago | `app/ai/agents.py` (CAFETERIA_PROMPT) |
| Kit Festou pós-pedido | `app/ai/agents.py` (todos os *_ORDER_PROMPT) |
| Anti-dedução | `app/ai/agents.py` (CAKE_ORDER_PROMPT) |
| Links/cardápio | `app/ai/runner.py`, `app/ai/agents.py` (TRIAGE_PROMPT) |
| Debounce | `app/api/routes/webhook.py`, `app/ai/runner.py` |
| Welcome message | `app/welcome_message.py`, deploy |
| Páscoa | `app/ai/policies.py`, `app/ai/runner.py` |
| Teste filtro | `app/api/routes/webhook.py`, `app/settings.py` |
| Motivos escalação | `app/ai/agents.py`, `app/ai/tools.py` |
| Resumo padronizado | `app/ai/agents.py` (todos os *_ORDER_PROMPT) |
| Mídia | `app/ai/runner.py` |
| Testes | `tests/test_ai_policies.py`, `tests/test_ai_agent_prompts.py`, `tests/test_sprint5_regression.py` |
