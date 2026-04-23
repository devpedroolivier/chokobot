# TODO — Demandas 2026-04-23

Lista de modificações solicitadas para o Chokobot, organizadas por prioridade,
área e arquivos prováveis de impacto.

> **Status atual (2026-04-23):** itens #1–6 implementados; suíte 318/318 passando
> (9 tests novos). Itens #7 e #8 dependem do cliente. Changelog técnico em
> [CHANGELOG_DEMANDAS_2026-04-23.md](CHANGELOG_DEMANDAS_2026-04-23.md).

---

## Sumário rápido

| # | Demanda | Área | Prioridade | Status |
|---|---------|------|------------|--------|
| 1 | Correção de envio de mensagens pelo painel | Frontend + Backend | P0 | ✅ |
| 2 | Captura imediata de conversas (números não salvos) | Frontend + Backend | P0 | ✅ |
| 3 | Mensagens prontas com identificação do atendente | Frontend | P1 | ✅ |
| 4 | Contexto da Trufinha — finalidade/ocasião do bolo | IA | P1 | ✅ |
| 5 | Regras de tamanho: B6/B7 ≥ 30 pessoas, P4/P6 ≤ 20 | IA | P1 | ✅ |
| 6 | Agendamento automático Trufinha (sex 19h ↔ seg 06h) | Backend | P1 | ✅ |
| 7 | Apresentar resultados das implementações no mesmo dia | Processo | P1 | ⏳ (envio ao cliente) |
| 8 | Avaliar aquisição de domínio `chocodelicia.com.br` | Infra/Negócio | P2 | ⏳ (decisão) |

---

## 1. Correção de envio de mensagens pelo painel — **P0**

**Problema:** envio de mensagens pelo painel admin não está funcionando.

**Tarefas**
- [ ] Reproduzir o bug (qual rota? que erro? front ou back?)
- [ ] Investigar fluxo: `frontend/src/components/inbox.tsx` → endpoint do backend → gateway Z-API
- [ ] Conferir endpoint que dispara mensagem outbound (provável `app/api/routes/painel.py` ou rota dedicada)
- [ ] Validar credenciais Z-API (`ZAPI_TOKEN`, `ZAPI_BASE`) no ambiente em uso
- [ ] Adicionar/ajustar log de erro do gateway para diagnóstico
- [ ] Teste E2E manual: enviar mensagem pelo painel → confirmar entrega no WhatsApp
- [ ] Adicionar teste automatizado em `tests/` cobrindo o caminho de envio

**Critério de aceite:** envio funciona consistentemente em produção e há cobertura de teste.

**Pergunta aberta:** qual o sintoma exato? (silencioso, 4xx/5xx, mensagem some, etc.)

---

## 2. Captura imediata de conversas (números não salvos) — **P0**

**Problema:** conversas de números não cadastrados não aparecem imediatamente no painel.

**Tarefas**
- [ ] Revisar listagem do inbox — `frontend/src/components/inbox.tsx` + `frontend/src/lib/use-live-panel-snapshot.ts`
- [ ] Conferir backend: `app/api/routes/painel.py` e `app/application/use_cases/panel_dashboard.py`
- [ ] Verificar criação automática de cliente no `process_inbound_message.py` quando o número é desconhecido
- [ ] Garantir que toda mensagem inbound dispare atualização do snapshot do painel (live)
- [ ] Confirmar que o toggle ativar/desativar bot por conversa está disponível para esses contatos novos
- [ ] Teste manual: enviar mensagem de número novo → conversa aparece em < 5s no painel

**Critério de aceite:** qualquer mensagem recebida via Z-API aparece no inbox em tempo real, com botão para pausar/retomar o bot naquela conversa.

---

## 3. Mensagens prontas com identificação do atendente — **P1**

**Demanda:** ao assumir um chat humanizado, oferecer mensagens prontas que identifiquem o atendente (ex.: "Atendente Lu, oi! …").

**Tarefas**
- [ ] Definir lista inicial de templates (com placeholder `{atendente}`)
- [ ] Definir cadastro de atendentes — sugestão: env `PANEL_ATTENDANTS=Lu,Ana,...` ou tabela dedicada
- [ ] UI: dropdown de "Quem está atendendo" + botões de templates rápidos no `inbox.tsx`
- [ ] Persistir o atendente ativo da sessão (localStorage ou cookie do painel)
- [ ] Registrar nos eventos de domínio qual atendente humano enviou cada mensagem (auditoria)

**Critério de aceite:** atendente seleciona o nome uma vez por sessão e usa templates que já vêm preenchidos com sua identificação.

**Pergunta aberta:** a lista de atendentes é fixa ou precisa de CRUD no painel?

---

## 4. Contexto da Trufinha — finalidade e ocasião do bolo — **P1**

**Demanda:** a Trufinha precisa entender a ocasião (aniversário, casamento, chá de bebê, etc.) e nº de convidados antes de recomendar.

**Tarefas**
- [ ] Atualizar prompt do `CakeOrderAgent` em `app/ai/agents.py` para sempre coletar: ocasião, nº de pessoas, data desejada, restrições
- [ ] Atualizar `app/ai/knowledge/menus.md` com tabela explícita ocasião → linha sugerida
- [ ] Adicionar exemplos few-shot no agente cobrindo casamento, aniversário infantil, aniversário adulto, chá de bebê, corporativo
- [ ] Tool/função para registrar essas variáveis no estado da conversa (se ainda não houver)
- [ ] Testes em `tests/` cobrindo: agente pergunta ocasião antes de recomendar; agente não recomenda sem saber nº de pessoas

**Critério de aceite:** em ≥ 95% dos diálogos de bolo, a Trufinha pergunta ocasião + nº de pessoas antes da primeira recomendação.

---

## 5. Regras de tamanho — retangulares vs. redondos — **P1**

**Regra de negócio**
- Festas com **mais de 30 pessoas** → priorizar **bolos retangulares (B6, B7)**
- Bolos redondos **P4 e P6** → limite de **até 20 pessoas**
- Faixa intermediária (21–30) → confirmar com cliente / sugerir B-line

**Tarefas**
- [ ] Centralizar regra em `app/services/commercial_rules.py` (função `recommend_cake_format(num_pessoas) -> list[str]`)
- [ ] Expor via tool ao `CakeOrderAgent` em `app/ai/tool_registry.py`
- [ ] Atualizar `app/ai/knowledge/menus.md` com tabela de capacidade por modelo
- [ ] Hard-block: agente não deve oferecer P4/P6 quando `num_pessoas > 20`
- [ ] Testes unitários em `tests/` para a função e teste de integração para o agente

**Critério de aceite:** nenhuma recomendação de P4/P6 para >20 pessoas; recomendação primária = B6/B7 quando >30.

---

## 6. Agendamento automático Trufinha (sex 19h ↔ seg 06h) — **P1**

**Demanda:** desativar o bot automaticamente sex 19h e reativar seg 06h.

**Tarefas**
- [ ] Estender `app/services/store_schedule.py` com janela "AI ativa" separada da janela "loja aberta"
- [ ] Variáveis em `app/settings.py`: `AI_AUTO_OFF_WEEKDAY=4`, `AI_AUTO_OFF_HOUR=19`, `AI_AUTO_ON_WEEKDAY=0`, `AI_AUTO_ON_HOUR=6` (ou faixa em string única)
- [ ] No `process_inbound_message.py`: se `ai_active() == False`, não chamar runner OpenAI; encaminhar para fila humana e/ou autoresponder pré-definido
- [ ] Permitir override manual via flag (já existe `STORE_CLOSED`; criar `AI_DISABLED` análogo) e via painel
- [ ] Indicador no painel mostrando "Trufinha ativa/inativa" com motivo (agendado / manual)
- [ ] Testes cobrindo: sex 18:59 ativa, sex 19:01 inativa, sáb 12:00 inativa, seg 05:59 inativa, seg 06:00 ativa

**⚠️ Conflito a confirmar:** sábado é dia comercial (09–18 conforme CLAUDE.md). Se o bot fica off de sex 19h até seg 06h, **toda a operação de sábado fica sem Trufinha**. Confirmar com o cliente:
- (a) é isso mesmo (sábado é só atendimento humano)?
- (b) ou o off é apenas no domingo/madrugada?

---

## 7. Apresentar resultados das implementações no mesmo dia — **P1**

**Processo de entrega**
- [ ] Após implementar #4, #5 e #6, gravar/registrar testes manuais demonstrando comportamento
- [ ] Preparar changelog curto (1 página) com: o que mudou, como testar, riscos
- [ ] Compartilhar resultados no mesmo dia da implementação

---

## 8. Aquisição de domínio `chocodelicia.com.br` — **P2** (decisão)

**Sugestão comercial:** comprar o domínio (~R$ 40/ano) para profissionalismo, centralização e possível redução de custos.

**Tarefas**
- [ ] Confirmar disponibilidade em registro.br
- [ ] Definir titular (CNPJ da Chokodelícia)
- [ ] Mapear o que vai sob o domínio: painel admin, landing, e-mail profissional?
- [ ] Plano de DNS: subdomínios `painel.`, `api.`, `www.`
- [ ] Configurar TLS (Let's Encrypt ou Cloudflare)
- [ ] Atualizar `ADMIN_FRONTEND_URL` e CORS quando migrar

**Decisão pendente do cliente** antes de qualquer ação técnica.

---

## Ordem sugerida de execução

1. **Hoje:** #1 (envio painel) e #2 (captura imediata) — bloqueiam operação
2. **Hoje/amanhã:** #4, #5, #6 (mudanças de IA + agendamento) com testes — entregar #7 ao final
3. **Esta semana:** #3 (templates de atendente)
4. **Aguardando decisão:** #8 (domínio)

---

## Perguntas pendentes ao cliente

1. Qual o sintoma exato do bug de envio (#1)? Print/erro ajudaria.
2. Lista de atendentes para os templates (#3) — Lu + quais outros?
3. Cadastro de atendentes precisa ser editável pelo painel ou pode ficar fixo em config?
4. Sábado: Trufinha fica off mesmo durante o expediente (#6)? Confirmar janela.
5. Domínio (#8): seguimos com a compra?
