# Admin Modernization Rollout

## Escopo entregue

- endurecimento do runtime com validacao de schema e controle de fallback do backend de estado
- sincronizacao persistida entre atendimento, rascunho e pedido confirmado via `customer_processes`
- separacao visual e operacional entre atendimento e pedidos confirmados no painel
- reducao de falso positivo de pedido criado cedo demais nos fluxos de entrega e IA
- introducao do admin moderno em `Next.js + Tailwind CSS`
- autenticacao e sessao HTTP-only no admin moderno
- migracao das telas modernas de:
  - dashboard
  - clientes
  - detalhe de cliente
  - novo cliente
  - encomendas
  - detalhe de encomenda
  - nova encomenda
- acoes operacionais no admin moderno:
  - atualizar status da encomenda
  - criar cliente
  - editar cliente
  - excluir cliente
  - criar encomenda
  - excluir encomenda

## Rotas modernas disponiveis

- `/`
- `/login`
- `/clientes`
- `/clientes/novo`
- `/clientes/{id}`
- `/encomendas`
- `/encomendas/nova`
- `/encomendas/{id}`

## Integracao com FastAPI legado

- snapshots JSON para leitura operacional do painel, clientes e encomendas
- mutacoes JSON para clientes e encomendas
- redirects controlados por `ADMIN_FRONTEND_URL` para desviar rotas Jinja ja cobertas pelo frontend moderno

Rotas legadas ja preparadas para redirect:

- `/painel`
- `/painel/clientes`
- `/painel/clientes/novo`
- `/painel/clientes/{id}/editar`
- `/painel/encomendas`
- `/painel/encomendas/novo`
- `/painel/encomendas/{id}`

## Validacao realizada

- suite principal Python: `113` testes OK
- frontend:
  - `npm audit --omit=dev`: `0 vulnerabilities`
  - `npm run build`: OK em `Next.js 16.2.1`

## Pendencias remanescentes

- decidir o destino das telas legadas ainda fora do admin moderno:
  - `atendimentos`
  - `cafeteria`
  - `entregas`
  - variantes antigas de painel/listagens
- decidir se o painel moderno vai absorver exportacoes TXT ou se elas seguem no FastAPI
- revisar artefatos de runtime em `dados/` para evitar drift de arquivos rastreados no git
