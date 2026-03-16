# Executive Implementation Plan

## Objetivo
Evoluir o Chokobot de uma aplicacao funcional para uma base de produto replicavel, segura e preparada para escala, sem alterar as regras de negocio atuais.

Este plano foi adaptado ao estado atual do repositorio, considerando principalmente:
- arquitetura hibrida entre legado e camadas modernas
- uso misto de `sqlite3` direto e SQLAlchemy
- split parcial entre `edge` e `conversation`
- estado conversacional local/Redis
- observabilidade e seguranca ainda em nivel MVP

## Premissas
- Nao alterar logica comercial nem regras de atendimento.
- Priorizar reducao de risco operacional antes de novas features.
- Executar em sprints curtas, com entregas incrementais e verificaveis.
- Manter compatibilidade com a estrutura atual enquanto a consolidacao acontece.

## Estado Atual Resumido

### Pontos positivos
- `FastAPI` bem distribuido entre app principal, `edge` e `conversation`
- introducao de portas, gateways, use cases e buses internos
- testes cobrindo seguranca, observabilidade, split HTTP e partes do fluxo
- readiness, liveness e metricas basicas ja existem

### Principais gargalos
- coexistencia de legado e arquitetura nova no mesmo runtime
- dados acessados por varios estilos ao mesmo tempo
- estado e mensageria ainda muito locais
- bootstrap da IA com forte acoplamento ao ambiente
- empacotamento e automacao de engenharia ainda incompletos
- ausencia de modelo multi-tenant para transformar a solucao em produto

## Principios de Implementacao
- Nao reescrever tudo de uma vez.
- Consolidar primeiro a fundacao tecnica.
- Encapsular antes de substituir.
- Preferir migracoes pequenas, observaveis e reversiveis.
- Tornar o ambiente de desenvolvimento e deploy reproduziveis.

## Arquitetura-Alvo
- `api/`: interfaces HTTP e contratos externos
- `application/`: orchestracao, use cases, command bus, event bus
- `domain/`: contratos, entidades e regras estaveis
- `infrastructure/`: banco, gateways, mensageria, estado, templates
- `docs/`: arquitetura, operacao, roadmap e runbooks

### Diretrizes
- `app/routes` e `app/models` passam a ser tratados como legado em transicao
- novos fluxos e refactors entram pelo caminho `api -> application -> domain -> infrastructure`
- o codigo de `services` deve ser reduzido progressivamente em favor de use cases menores

## Roadmap Executivo por Sprint

### Sprint 1 - Fundacao e Higiene de Projeto
Objetivo: tornar o repositorio previsivel para desenvolvimento, teste e entrega.

#### Backlog
- criar `pyproject.toml` com dependencias de app e desenvolvimento
- padronizar comandos com `Makefile` ou scripts equivalentes
- criar `.env.example`
- criar `.dockerignore`
- revisar `.gitignore` para artefatos de runtime, banco local e caches
- converter `README.md` para UTF-8 e atualizar bootstrap do projeto
- padronizar descoberta e execucao da suite de testes
- criar pipeline de CI para lint, testes e build Docker

#### Impacto esperado
- onboarding mais rapido
- menos falhas de ambiente
- base pronta para colaboracao e deploy continuo

#### Criterios de saida
- qualquer desenvolvedor consegue subir o projeto seguindo a documentacao
- a suite principal roda com um unico comando
- push sem CI verde deixa de ser aceitavel

### Sprint 2 - Configuracao, Logging e Observabilidade
Objetivo: profissionalizar a operacao sem mudar comportamento.

#### Backlog
- centralizar configuracao em um unico modulo tipado
- substituir leituras dispersas de `os.getenv`
- padronizar logs estruturados em JSON
- remover `print` operacional do codigo de runtime
- evoluir `app/observability.py` para contrato mais consistente
- documentar logs, healthchecks e metricas
- preparar integracao futura com APM e error tracking

#### Impacto esperado
- diagnostico mais rapido de incidentes
- melhor rastreabilidade de erros
- operacao mais limpa em container e producao

#### Criterios de saida
- logs com `request_id` e eventos coerentes
- sem `print` relevante no caminho critico
- health/readiness documentados e confiaveis

### Sprint 3 - Testabilidade e Isolamento da IA
Objetivo: estabilizar o nucleo de IA e eliminar dependencias de ambiente no import.

#### Backlog
- tornar lazy a inicializacao do client OpenAI
- injetar dependencias de IA para teste
- separar bootstrap de sessao, ferramentas e loop principal
- corrigir testes que falham por `OPENAI_API_KEY`
- definir estrategia de mocks/fixtures para fluxos AI
- documentar contrato das tools e dos agentes

#### Impacto esperado
- menor risco de regressao
- testes mais confiaveis
- evolucao do agente com menos acoplamento

#### Criterios de saida
- modulos de IA importam sem precisar de segredo real
- testes AI rodam em ambiente local e CI

### Sprint 4 - Consolidacao Arquitetural
Objetivo: reduzir a divida estrutural mantendo a logica atual intacta.

#### Backlog
- formalizar a arquitetura oficial do projeto
- isolar `app/routes` e `app/models` como legado em transicao
- limpar imports ociosos e dependencias cruzadas
- quebrar fluxos grandes em modulos menores por responsabilidade
- mover orquestracoes para `application/use_cases`
- reforcar a adocao de providers em `service_registry`

#### Impacto esperado
- menor custo de manutencao
- maior clareza arquitetural
- codigo mais facil de testar e evoluir

#### Criterios de saida
- novos desenvolvimentos nao entram mais pelo legado
- dependencias entre camadas ficam mais previsiveis

### Sprint 5 - Camada de Dados Pronta para Escala
Objetivo: consolidar o acesso a dados e preparar migracao segura para banco de producao.

#### Backlog
- definir SQLAlchemy + Alembic como padrao oficial
- parar de expandir uso de `sqlite3` direto
- criar baseline de migracao
- reduzir DDL em startup
- preparar `DATABASE_URL` de producao com Postgres
- revisar indices, constraints e consistencia de tabelas
- documentar estrategia de migracao e rollback

#### Impacto esperado
- base mais segura para concorrencia e crescimento
- menor acoplamento ao SQLite
- caminho claro para ambiente multi-instancia

#### Criterios de saida
- schema gerenciado por migracoes
- nova persistencia centralizada em repositorios padronizados

### Sprint 6 - Estado Distribuido e Mensageria Confiavel
Objetivo: remover fragilidade operacional em sessao, replay e envio de mensagens.

#### Backlog
- tornar Redis obrigatorio em producao
- adicionar TTL para sessao, deduplicacao e caches de replay
- substituir outbox JSONL por outbox persistente em banco
- criar worker de reprocessamento/envio
- reforcar idempotencia no webhook
- revisar retries e backoff dos gateways externos

#### Impacto esperado
- menos perda de evento e mensagem
- melhor comportamento sob carga
- suporte real a escalonamento horizontal

#### Criterios de saida
- estado compartilhado entre instancias
- retries previsiveis
- eventos reenfileiraveis com rastreabilidade

### Sprint 7 - Seguranca de Produto
Objetivo: sair do nivel MVP de seguranca para uma base comercial confiavel.

#### Backlog
- centralizar segredos e configuracoes sensiveis
- adicionar rate limiting
- proteger comunicacao interna entre servicos
- ampliar trilha de auditoria
- revisar estrategia de autenticacao do painel
- revisar redacao de logs e dados sensiveis
- documentar politicas minimas de acesso e operacao

#### Impacto esperado
- menor superficie de ataque
- mais confianca para operar com mais clientes
- menos risco reputacional

#### Criterios de saida
- endpoints criticos protegidos
- eventos sensiveis auditaveis
- segredos nao espalhados pelo codigo

### Sprint 8 - Produto Replicavel e Multi-tenant
Objetivo: transformar a aplicacao em plataforma replicavel para varias clientes.

#### Backlog
- introduzir conceito de `tenant`
- isolar configuracao por cliente
- externalizar cardapio, branding, links, horarios e learnings
- remover dados fixos de marca do codigo
- preparar painel e APIs para escopo por tenant
- documentar onboarding de nova cliente
- criar template de provisionamento

#### Impacto esperado
- possibilidade de atender varias lojas sem fork do codigo
- menor custo de entrada de nova cliente
- base real para produto/SaaS

#### Criterios de saida
- configuracoes principais fora do codigo
- tenant identificado em runtime e persistencia

## Backlog Transversal
- ampliar cobertura de testes de integracao
- adicionar validacao estatica gradual
- documentar runbooks operacionais
- documentar padroes de logs, eventos e naming
- revisar experiencia do painel sem alterar fluxo funcional

## Ordem Recomendada de Execucao
1. Sprint 1
2. Sprint 2
3. Sprint 3
4. Sprint 4
5. Sprint 5
6. Sprint 6
7. Sprint 7
8. Sprint 8

## Dependencias Entre Sprints
- Sprint 3 depende da padronizacao basica de ambiente da Sprint 1
- Sprint 4 depende de testes minimamente estaveis
- Sprint 5 depende da arquitetura mais consolidada
- Sprint 6 depende de direcao clara da camada de dados
- Sprint 8 depende da base operacional e de seguranca estar madura

## Indicadores de Sucesso
- tempo de onboarding tecnico menor que 30 minutos
- testes executando de forma reprodutivel em CI
- logs estruturados e pesquisaveis
- schema controlado por migracoes
- estado distribuido em producao
- onboarding de nova cliente sem fork do projeto

## Fora de Escopo Neste Plano
- mudar regras de atendimento
- reescrever os fluxos de negocio
- alterar catalogo comercial
- mudar comportamento do agente para cliente final

## Resultado Esperado
Ao final desse roadmap, o Chokobot deixa de ser apenas uma automacao funcional para uma loja e passa a ter fundacao tecnica para operar como produto replicavel, com mais seguranca, melhor observabilidade, menor custo de manutencao e caminho claro para escalar.
