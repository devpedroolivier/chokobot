# Decisões — Fase B (cutover Postgres + multi-tenant)

**Status:** ✅ aprovadas em 2026-04-26 — todas as recomendações aceitas.
**Data:** 2026-04-26
**Contexto:** consolidação das decisões espalhadas em `docs/PIVOT_TODO.md`
e `docs/MULTI_TENANT.md`.

## Resumo das respostas

| # | Decisão | Resposta |
|---|---|---|
| 1 | Postgres separado vs compartilhado | **A — separado (`chokobot-postgres`)** |
| 2 | Driver | **A — psycopg3 async + SQL raw** |
| 3 | Segundo tenant | Em aberto — bloqueia Fase D, **não** bloqueia B |
| 4 | Janela de downtime | **A — terça 09:00** |
| 5 | Header platform admin | **A — "Trufinha" no admin global** |
| 6 | Tabela `atendimentos` | **A — manter com `tenant_id`** |
| 7 | Outbox JSONL | **A — migrar para tabela Postgres com `tenant_id`** |
| 8 | Branding | **C (piloto)** — paleta default + `display_name` + `logo_url` |
| 9 | Onboarding concierge | **B — assistente executa via instruções** |
| 10 | Telemetria por tenant | **A — `tenant_id` em logs/métricas desde Fase B.4** |

**Próximo passo:** B.1 (subir Postgres no compose) + B.2 (migrations).

---

## 1. Postgres separado ou compartilhado com Evolution?

Hoje rodamos `evolution-postgres` (banco do Evolution API) no Compose.

**Opções:**
- **A — Subir `chokobot-postgres` separado.** Volume próprio, ciclo de vida próprio, backup independente. **+1 container.**
- B — Reaproveitar `evolution-postgres` adicionando outro database.

**Recomendação: A.** Backup do Trufinha pode acontecer numa janela; Evolution não pode parar. Misturar dificulta restore parcial. Custo do container extra é desprezível.

> 👉 **Sua resposta:** _____

---

## 2. Driver: psycopg3 raw ou SQLAlchemy ORM?

**Opções:**
- **A — psycopg3 async + SQL raw.** Mantém os repositórios atuais (que já fazem SQL na mão). Migração mais rápida. Sem nova abstração para aprender.
- B — SQLAlchemy ORM completo. Models declarativos, autogenerate de migration, type safety. Refactor maior nos repositórios.
- C — SQLAlchemy Core (apenas Query builder, sem ORM). Meio termo.

**Recomendação: A.** A Fase B já é grande (schema + cutover + isolamento). Adicionar ORM em cima é amplificar risco. Pode virar SQLAlchemy depois (Fase E ou separado).

> 👉 **Sua resposta:** _____

---

## 3. Quem é o segundo tenant (confeitaria piloto)?

**Pré-requisito:** sem segundo tenant identificado, Fase D (painel multi-tenant) e onboarding concierge perdem propósito.

**Perguntas para você:**
- Nome / razão social: _____
- Cidade / fuso (se diferente de America/Sao_Paulo): _____
- Quem é o contato decisor que assina a parceria-piloto: _____
- Quando podem fornecer os dados (catálogo, horários, branding mínimo, telefone WhatsApp): _____
- Existe relação prévia com Chokodelícia (parceria, indicação, relacionamento comercial)? _____

**Pode ser:** "ainda não sei, vou achar nas próximas 2 semanas". Aceitável — mas registrar como bloqueio para Fase D.

> 👉 **Sua resposta:** _____

---

## 4. Janela de downtime para o cutover SQLite → Postgres

A migração de dados toma 10–15 min. Durante esse tempo o WhatsApp não responde (pode ser feito com `STORE_CLOSED=1` para enviar aviso automático).

**Opções:**
- **A — Terça 09:00.** Recomendação do `MULTI_TENANT.md`. Início da semana, antes do pico de bolo do dia (cutoff é 11:00).
- B — Domingo de manhã (loja fechada). Risco zero de cliente, mas se algo der errado, segunda já volta com produção quebrada.
- C — Madrugada de uma terça (02:00–03:00). Cliente quase zero, mas equipe técnica também precisa estar acordada.

**Recomendação: A** — todo mundo desperto, time da Chokodelícia sabe avisar clientes se travar.

> 👉 **Sua resposta:** _____

---

## 5. Nome do produto (Trufinha) vs nome do tenant (Chokodelícia)

Rebranding de marca já foi aplicado. Pendência: na hora do **painel platform admin** (`/admin`) que vai gerenciar todos os tenants, o que aparece no header?

**Opções:**
- **A — Header "Trufinha" no admin global.** Cada tenant_admin vê o nome do tenant dele no header de `/t/{slug}/...`.
- B — Header dinâmico, sempre o nome do tenant ativo. Platform admin sem tenant ativo mostra "Trufinha".

**Recomendação: A.** Mais previsível. B confunde quando o platform admin alterna entre tenants.

Submarca pra evolução comercial: o produto pode ter um codinome de empresa diferente do nome técnico em algum momento (ex.: "Trufinha by ChocoTech"). Não afeta o código agora — apenas branding visual.

> 👉 **Sua resposta:** _____

---

## 6. Tabela `atendimentos` — dropar ou manter?

A tabela existe no schema mas tem **0 linhas** em produção. Propósito original esquecido.

**Opções:**
- **A — Manter na migration multi-tenant** (com `tenant_id`) por precaução. Custo: ~zero.
- B — Dropar na migration. Schema mais limpo.

**Recomendação: A.** O custo de manter é zero. Se descobrirmos que era importante depois, evitamos ter que recriar.

> 👉 **Sua resposta:** _____

---

## 7. Outbox JSONL — migrar para tabela Postgres ou manter por tenant?

Hoje `dados/outbox.jsonl` guarda mensagens enfileiradas quando o gateway WhatsApp falha. É append-only, lido pelo `scripts/reprocess_outbox.py`.

**Opções:**
- **A — Migrar para tabela `outbox` no Postgres** com `tenant_id`. Consultável, indexável, transacional junto com o pedido.
- B — Manter JSONL, com arquivo separado por tenant: `dados/outbox_{tenant_slug}.jsonl`.
- C — Manter como está (compartilhado). Inseguro: tenant 1 lê outbox de tenant 2 no reprocess.

**Recomendação: A.** Custo razoável (uma tabelinha) e ganho de operação enorme (queries SQL em vez de grep em arquivo).

> 👉 **Sua resposta:** _____

---

## 8. Branding tokenizável — quem desenha?

Para cada tenant suportar logo, paleta, nome longo, nome curto e mensagens-chave próprias, precisamos definir o **schema do `tenant_config.branding`**:

```jsonc
{
  "display_name": "Chokodelícia",       // nome longo no painel
  "short_name": "Choko",                 // saudação curta
  "logo_url": "https://...",
  "primary_color": "#cf6f4f",
  "secondary_color": "#fce4d6",
  "social_handle": "@chokodelicia",
  "welcome_message_template": "Olá! Que bom ter você aqui na *{short_name}*! ...",
  "easter_link": "https://pascoachoko.goomer.app",  // opcional, por tenant
  "panel_attendants": ["Lu"]
}
```

**Quem precisa decidir:**
- (A) Você define o schema técnico (chaves esperadas) — eu implemento.
- (B) Você + designer/UX definem o visual e os limites (cores, fontes, tom). Eu implemento o pipeline.
- (C) Não temos designer agora; usamos uma paleta default e cada tenant entra com `display_name` + `logo_url`. Visual fica padronizado.

**Recomendação: C** para o piloto, **B** quando tiver 3+ tenants no ar.

> 👉 **Sua resposta:** _____

---

## 9. Onboarding concierge — quem opera?

A Fase D inclui `scripts/create_tenant.py` para criar o tenant + instância Evolution + QR. **Quem roda esse script?**

**Opções:**
- A — Você manualmente, via SSH no servidor.
- **B — Eu (assistente) executo via instruções, com você confirmando cada passo.**
- C — Endpoint admin protegido que recebe POST com os dados.

**Recomendação: B** para o piloto (1–3 tenants), **C** quando virar volume.

> 👉 **Sua resposta:** _____

---

## 10. Telemetria por tenant desde a Fase B?

Métricas e logs hoje não tem `tenant_id`. Quando Fase B implantar, podemos:

**Opções:**
- **A — Adicionar `tenant_id` em todo log + label nas métricas Prometheus já no PR de Fase B.4.** Zero custo extra de implementação.
- B — Deixar pra Fase E (Hardening). Risco: descobrimos custos OpenAI altos sem saber qual tenant está consumindo.

**Recomendação: A.** É barato e abre visibilidade desde o dia 1.

> 👉 **Sua resposta:** _____

---

## Bloqueios & ordem

| Item | Bloqueia |
|---|---|
| 1, 2 | Início da Fase B (escolha de Postgres + driver) |
| 4 | Cutover (data marcada) |
| 3 | Fase D end-to-end (sem 2º tenant não tem o que onboardar) |
| 5, 6, 7, 8, 10 | Detalhes da Fase B/D — podem ser respondidos depois mas afetam migrations |
| 9 | Operação real do onboarding |

**Mínimo para destravar Fase B:** decisões 1, 2 e 4.
**Mínimo para destravar Fase D:** decisão 3 (segundo tenant identificado).

---

## Como responder

Você pode editar este arquivo direto e me mandar de volta, ou só responder aqui no chat com algo tipo:
> "1 = A, 2 = A, 3 = ainda não, 4 = terça 09:00, 5 = A, 6 = A, 7 = A, 8 = C por enquanto, 9 = B, 10 = A"

Depois disso eu sigo com a Fase B.1 (subir Postgres no Compose).
