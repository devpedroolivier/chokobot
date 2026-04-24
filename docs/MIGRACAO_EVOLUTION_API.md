# Migração Z-API → Evolution API

**Status:** proposta — aguardando aprovação antes de implementar.
**Data:** 2026-04-23.
**Motivo imediato:** instância Z-API bloqueada (`"To continue sending a message,
you must subscribe to this instance again"`). Oportunidade de sair de um
fornecedor pago para uma stack self-hosted open source.

---

## 1. Visão executiva

- **Evolution API v2** é um servidor Node.js open source (repo
  [EvolutionAPI/evolution-api](https://github.com/EvolutionAPI/evolution-api))
  que integra com WhatsApp via a lib Baileys. Mesma família funcional do
  Z-API, mas self-hosted.
- Instalação: Docker (1 container app + Postgres + Redis).
- Custo: zero de licença. Custo de infra: baixo (~sobe no mesmo host atual).
- **Trade-off:** Baileys usa protocolo não-oficial do WhatsApp Web. Risco de
  ban de número é igual ou um pouco superior ao Z-API. Vale contingência de
  um número alternativo.
- Estratégia: **Adapter Pattern com feature flag**, permitindo rollback em
  segundos sem mexer no código.

---

## 2. Mapa atual do Z-API (footprint no Chokobot)

### 2.1 Outbound (envio)

| Arquivo | Papel |
|---------|-------|
| `app/infrastructure/gateways/zapi_messaging_gateway.py` | Classe `ZapiMessagingGateway.send_text(phone, mensagem) -> bool`. Usa `POST {ZAPI_BASE}/send-text` com header `Client-Token` e payload `{phone, message}`. Retry + outbox. |
| `app/application/service_registry.py:49-52` | Factory `@lru_cache def get_messaging_gateway()` → `ZapiMessagingGateway()`. |
| `app/settings.py:52-53, 107-116` | Envs `ZAPI_TOKEN`, `ZAPI_BASE` + properties `zapi_endpoint_text`/`zapi_endpoint_image`. |

### 2.2 Inbound (webhook)

| Arquivo | Papel |
|---------|-------|
| `app/api/routes/webhook.py:92-156` | Rota `POST /webhook`. Filtra `fromMe`, `DeliveryCallback`, grupos, Goomer-auto. |
| `app/utils/payload.py:111-118` (`normalize_incoming`) | Extrai `text`, `phone`, `chat_name`, `message_id`, `message_type` do payload Z-API. |
| `app/security.py:128-148` | `verify_webhook_secret` genérico — header configurável via `WEBHOOK_SECRET_HEADER`. **Reutilizável**. |

### 2.3 Outros

| Arquivo | Papel |
|---------|-------|
| `scripts/reprocess_outbox.py` | Drena `dados/outbox.jsonl` via Z-API. |
| `.env.example:2-3` | `ZAPI_TOKEN`, `ZAPI_BASE`. |
| `app/config.py:18-21` | Log dos envs. |
| ~50 arquivos de teste | `os.environ.setdefault("ZAPI_TOKEN", "test-token")` e `ZAPI_BASE=https://example.test`. |
| `CLAUDE.md`, `README.md`, `docs/sprints-atendimento.md` | Menções textuais. |

**Nenhum HTTP direto a `api.z-api.io` fora do gateway.** Boa notícia — a migração fica isolada.

---

## 3. Evolution API — referência técnica

### 3.1 Endpoints principais

| Ação | Método + URL | Header | Body |
|------|--------------|--------|------|
| Criar instância | `POST {server}/instance/create` | `apikey: {API_KEY}` | `{instanceName, integration: "WHATSAPP-BAILEYS", webhook: {url, events: ["MESSAGES_UPSERT"]}}` |
| Conectar (QR) | `GET {server}/instance/connect/{instance}` | `apikey` | — |
| Enviar texto | `POST {server}/message/sendText/{instance}` | `apikey` | `{number: "5511999999999", text: "...", delay?: 1500, linkPreview?: false}` |
| Configurar webhook | `POST {server}/webhook/set/{instance}` | `apikey` | `{url, enabled: true, events: ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]}` |
| Status da instância | `GET {server}/instance/connectionState/{instance}` | `apikey` | — |

### 3.2 Payload inbound (evento `MESSAGES_UPSERT`)

```json
{
  "event": "messages.upsert",
  "instance": "chokodelicia",
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "fromMe": false,
      "id": "3EB0ABC123..."
    },
    "pushName": "Ana",
    "messageTimestamp": 1745423700,
    "message": {
      "conversation": "Oi, quero um bolo"
    }
  }
}
```

- **Grupos:** `remoteJid` termina em `@g.us` (vs `@s.whatsapp.net` para direct)
- **Texto:** pode vir em `data.message.conversation` (simples) ou
  `data.message.extendedTextMessage.text` (com link, reply, etc.)
- **Mídia:** `data.message.imageMessage.caption`, `audioMessage`, etc.
  (adiamos — nosso bot hoje só lida com texto).

### 3.3 Infra Docker

A stack Evolution API requer Postgres + Redis. O Chokobot já tem Redis (vai
compartilhar). Postgres é novo — adicionamos `evolution-postgres` dedicado.

---

## 4. Arquitetura alvo

```
┌─────────────────────────────────────────────────────────┐
│                    docker-compose.yml                   │
│                                                         │
│  chokobot (FastAPI)   ←→  chokobot-redis   (existente) │
│       ↓                                                 │
│  get_messaging_gateway()                                │
│    if MESSAGING_PROVIDER == "evolution":                │
│       → EvolutionMessagingGateway                       │
│    else:                                                │
│       → ZapiMessagingGateway                            │
│                                                         │
│  evolution-api (Node)  ←→  evolution-redis              │
│                         ←→  evolution-postgres          │
│                                                         │
│  chokobot-admin (Next.js)                               │
└─────────────────────────────────────────────────────────┘

 WhatsApp (via Baileys session)  ←→  evolution-api
                                        ↓ webhook
                                    /webhook (FastAPI)
```

Decisão de rota do webhook: **uma única rota `/webhook`** detecta o shape
automaticamente em `normalize_incoming()`. Rota separada `/webhook/evolution`
é fallback se quisermos isolamento total.

---

## 5. Plano em fases

### Fase 1 — Infra (sem tocar na Trufinha em produção)

1. Adicionar ao `docker-compose.yml`:
   - `evolution-postgres` (postgres:15)
   - `evolution-redis` (redis:latest) — ou reutilizar o `chokobot-redis` com DB diferente
   - `evolution-api` (evoapicloud/evolution-api:latest)
2. Criar `.env` de evolução com:
   - `AUTHENTICATION_API_KEY` — gerar com `openssl rand -hex 32`
   - `SERVER_URL=http://evolution-api:8080` (interno)
   - `DATABASE_CONNECTION_URI=postgresql://...`
   - `CACHE_REDIS_URI=redis://evolution-redis:6379/0`
3. `docker compose up -d evolution-postgres evolution-api`
4. `curl -X POST {server}/instance/create` para criar a instância `chokodelicia`
5. Abrir `http://host:8080/manager` (ou fetch `/instance/connect/chokodelicia`) e
   **escanear o QR pelo celular da Chokodelícia** — mesma conta que estava no Z-API
6. Confirmar `connectionState=open`

**Bloqueio humano:** alguém precisa escanear o QR.

### Fase 2 — Adapter backend

1. Criar `app/infrastructure/gateways/evolution_messaging_gateway.py` com
   `EvolutionMessagingGateway.send_text(phone, mensagem) -> bool`
   - Mesma assinatura e contrato do Z-API (drop-in)
   - Retry/backoff/outbox preservados (extrair lógica comum pra mixin/base)
2. Extender `app/settings.py`:
   - `messaging_provider: str = "zapi"` (env `MESSAGING_PROVIDER`, default `zapi` pra não quebrar)
   - `evolution_server_url`, `evolution_api_key`, `evolution_instance`
3. Atualizar `app/application/service_registry.py:49-52`:
   ```python
   @lru_cache
   def get_messaging_gateway():
       if get_settings().messaging_provider == "evolution":
           return EvolutionMessagingGateway()
       return ZapiMessagingGateway()
   ```
4. Refatorar `scripts/reprocess_outbox.py` pra usar o gateway atual via factory
   (em vez de falar direto com Z-API).

### Fase 3 — Webhook inbound

1. Atualizar `app/utils/payload.py::normalize_incoming()`:
   - Detecção: payload tem `data.key.remoteJid` → Evolution; senão cai no shape Z-API
   - Extrair:
     - `phone` ← `data.key.remoteJid.split("@")[0]`
     - `text` ← `data.message.conversation` ou `data.message.extendedTextMessage.text`
     - `chat_name` ← `data.pushName`
     - `message_id` ← `data.key.id`
     - `fromMe` ← `data.key.fromMe`
     - `is_group` ← `data.key.remoteJid.endswith("@g.us")`
2. Ajustar filtros em `webhook.py` para trabalhar com campos normalizados
   (hoje eles olham `body.get("fromMe")` direto — vale mover pra `normalize_incoming`).
3. Configurar webhook da instância Evolution:
   ```bash
   curl -X POST {server}/webhook/set/chokodelicia \
     -H "apikey: ${EVOLUTION_API_KEY}" \
     -d '{"url":"https://chokobot/webhook","enabled":true,
         "events":["MESSAGES_UPSERT"]}'
   ```

### Fase 4 — Testes

1. Novo test file `tests/test_evolution_messaging_gateway.py` espelhando
   `test_messaging_gateway.py`.
2. Novo test em `tests/test_normalize_incoming.py` (ou similar) cobrindo:
   - Payload Evolution direct
   - Payload Evolution grupo (deve setar `is_group`)
   - Payload Z-API legado (retrocompat)
3. Atualizar `scripts/run_tests.py` com:
   ```python
   "EVOLUTION_SERVER_URL": "http://evolution.test",
   "EVOLUTION_API_KEY": "test-key",
   "EVOLUTION_INSTANCE": "test",
   "MESSAGING_PROVIDER": "zapi",  # default pra não afetar tests existentes
   ```

### Fase 5 — Cutover

**Pré-requisitos:**
- Fase 1–4 merged na main
- `docker compose up --build -d` rodado
- Instância Evolution conectada (QR escaneado, connectionState=open)
- Smoke test manual: curl `sendText` direto pro Evolution entrega no WhatsApp teste

**Execução:**
1. Drenar/arquivar `dados/outbox.jsonl` (mesma lógica que fizemos hoje)
2. Flipar no `.env`: `MESSAGING_PROVIDER=evolution`
3. `docker compose up -d chokobot` (não precisa rebuild, só restart)
4. Smoke test pelo painel:
   - Mandar mensagem manual → confirmar chegada no WhatsApp real
   - Receber mensagem → confirmar aparecer no inbox em <5s
5. Observar 24h com Z-API ainda disponível como rollback

### Fase 6 — Arquivar Z-API

Após 1 semana estável:
1. Remover `ZapiMessagingGateway` e referências
2. Apagar envs `ZAPI_TOKEN`, `ZAPI_BASE` do `.env` e `.env.example`
3. Limpar `docs/` + `CLAUDE.md` + `README.md`
4. Cancelar assinatura Z-API (ação financeira)

---

## 6. Variáveis de ambiente propostas

Adicionar ao `.env` (e documentar em `.env.example`):

```env
# Provider escolhido: zapi (legado) ou evolution
MESSAGING_PROVIDER=zapi

# Evolution API
EVOLUTION_SERVER_URL=http://evolution-api:8080
EVOLUTION_API_KEY=<gerar com openssl rand -hex 32>
EVOLUTION_INSTANCE=chokodelicia

# Evolution DB (apenas infra — não lida pelo app)
EVOLUTION_DB_USER=evolution
EVOLUTION_DB_PASS=<gerar>
EVOLUTION_DB_NAME=evolution_db
```

Envs Z-API ficam no `.env` durante Fases 1–5 para permitir flip instantâneo.

---

## 7. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Ban do número WhatsApp (Baileys é unofficial) | Média | Alto | Ter número backup. Configurar `CONFIG_SESSION_PHONE_CLIENT` crível. Evitar mass-send. |
| QR session cai (celular offline, troca de aparelho) | Alta ao longo do tempo | Médio | Monitorar `connectionState`. Alerta via `CONNECTION_UPDATE` webhook. |
| Mudança de API do WhatsApp quebra Baileys | Baixa–Média | Alto | Manter Evolution API atualizada. Versão pinada no compose. |
| Perda de mensagens no cutover | Média | Médio | Drenar outbox antes. Avisar operação. Fazer em horário de baixo volume. |
| Payload webhook diferente do esperado | Média | Baixo | Testes de integração com fixtures reais. Log de payloads desconhecidos. |
| Postgres cresce sem limite | Média | Baixo | Monitorar volume. Postgres tem retention policy no Evolution v2. |

---

## 8. Checklist de aprovação

Me responde sobre cada item antes de começar:

- [ ] **Go/No-Go geral:** podemos migrar?
- [ ] **Número WhatsApp:** qual número vai no QR Evolution? O mesmo que está no Z-API? Tem backup?
- [ ] **Quando escanear o QR:** alguém da Chokodelícia disponível para escanear o QR do celular da loja? Sugestão: horário comercial, preferencialmente com a Lu junto.
- [ ] **Janela de cutover:** qual dia/hora de menor volume? Sugestão: terça 09:30 (após bolo do dia abrir, fluxo mais baixo).
- [ ] **Z-API atual:** renovar assinatura (para desbloquear envio agora) ou manter bloqueada até cutover?
- [ ] **Domínio/URL webhook:** a Evolution precisa apontar o webhook para uma URL pública do Chokobot. Hoje: `http://191.101.235.185:8003/webhook`. Fica como está ou migramos para domínio (ligação com demanda #8 do TODO)?
- [ ] **Dedicar Redis separado ou reaproveitar o do Chokobot** (DBs separados)?
- [ ] **Orçamento de infra:** Postgres novo custa ~200 MB de RAM. Host aguenta?

---

## 9. Próximos passos (se aprovado)

1. Eu mergo um PR da **Fase 1 + 2** (infra + adapter com flag default=zapi)
2. Subo Evolution API em paralelo ao Z-API
3. Escaneamos o QR (hora a combinar)
4. Smoke test com `MESSAGING_PROVIDER=evolution` em ambiente isolado
5. PR da **Fase 3 + 4** (webhook + tests)
6. Cutover (Fase 5) na janela combinada
7. Observação 7 dias → Fase 6

**Tempo estimado:** 4–6 horas de implementação + coordenação do QR. Sugiro fazer em duas sessões.

---

## 10. Referências

- [Evolution API docs](https://doc.evolution-api.com/v2/en/get-started/introduction)
- [Send text endpoint](https://doc.evolution-api.com/v2/api-reference/message-controller/send-text)
- [Webhooks configuration](https://doc.evolution-api.com/v2/en/configuration/webhooks)
- [GitHub repo](https://github.com/EvolutionAPI/evolution-api)
- [docker-compose.yaml oficial](https://github.com/EvolutionAPI/evolution-api/blob/main/docker-compose.yaml)
