# Plano Executivo de Implementacao

## Resumo Executivo
O Chokobot ja demonstra viabilidade funcional, mas ainda opera com fragilidades tipicas de um MVP: coexistencia de arquitetura legada com camadas novas, acesso a dados por multiplos estilos, dependencias de ambiente no nucleo de IA e lacunas operacionais em observabilidade, seguranca e estado distribuido.

O foco deste plano e reduzir risco operacional antes de acelerar novas frentes de produto. A execucao proposta privilegia estabilizacao do ambiente, consolidacao arquitetural, padronizacao da camada de dados e preparo para operacao distribuida, preservando a logica de negocio atual.

O resultado esperado nao e apenas um sistema mais organizado. E uma base de produto replicavel, com menor custo de manutencao, pronta para escalar tecnicamente e capaz de suportar evolucao multi-tenant sem reabrir decisoes estruturais fundamentais.

## Objetivo
Evoluir o Chokobot de uma aplicacao funcional para uma base de produto replicavel, segura e preparada para escala, sem alterar as regras de negocio atuais.

Este plano foi adaptado ao estado atual do repositorio, considerando principalmente:
- arquitetura hibrida entre legado e camadas modernas
- uso misto de `sqlite3` direto e SQLAlchemy
- separacao parcial entre `edge` e `conversation`
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

## Decisoes Estruturais Antecipadas
- O modelo de `tenant` precisa ser definido antes da consolidacao final da camada de dados, mesmo que a ativacao comercial multi-tenant aconteca depois.
- Eventos entre servicos precisam de contrato canonico, versionamento e regras claras de idempotencia.
- Cada servico extraido deve ter responsabilidade explicita sobre dados, APIs e operacao.
- A separacao atual entre `edge` e `conversation` deve ser tratada como etapa de validacao arquitetural, nao como indicativo de prontidao produtiva.

### Diretrizes
- `app/routes` e `app/models` passam a ser tratados como legado em transicao
- novos fluxos e refactors entram pelo caminho `api -> application -> domain -> infrastructure`
- o codigo de `services` deve ser reduzido progressivamente em favor de use cases menores

## Prioridades Imediatas
1. Tornar o repositorio reproduzivel para desenvolvimento, testes e entrega.
2. Eliminar acoplamentos de ambiente no nucleo de IA e no carregamento da aplicacao.
3. Formalizar contratos arquiteturais antes de expandir a extracao de servicos.
4. Consolidar a camada de dados com migracoes e direcao clara para Postgres.
5. Preparar estado distribuido, mensageria confiavel e trilhas minimas de seguranca operacional.

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
- definir contratos canonicos de eventos e responsabilidade inicial por limite de servico
- definir o modelo estrutural de `tenant` para APIs, eventos e persistencia

#### Impacto esperado
- menor custo de manutencao
- maior clareza arquitetural
- codigo mais facil de testar e evoluir

#### Criterios de saida
- novos desenvolvimentos nao entram mais pelo legado
- dependencias entre camadas ficam mais previsiveis
- contratos principais de integracao documentados

### Sprint 5 - Camada de Dados Pronta para Escala
Objetivo: consolidar o acesso a dados e preparar migracao segura para banco de producao.

#### Backlog
- definir SQLAlchemy + Alembic como padrao oficial
- parar de expandir uso de `sqlite3` direto
- criar baseline de migracao
- reduzir DDL em startup
- preparar `DATABASE_URL` de producao com Postgres
- refletir `tenant_id` e isolamento previsto no desenho de schema e repositorios
- revisar indices, constraints e consistencia de tabelas
- documentar estrategia de migracao e rollback

#### Impacto esperado
- base mais segura para concorrencia e crescimento
- menor acoplamento ao SQLite
- caminho claro para ambiente multi-instancia

#### Criterios de saida
- schema gerenciado por migracoes
- nova persistencia centralizada em repositorios padronizados
- decisoes de particionamento e isolamento por tenant registradas

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
- onboarding de nova operacao sem customizacao estrutural no codigo

## Backlog Transversal
- ampliar cobertura de testes de integracao
- adicionar validacao estatica gradual
- documentar runbooks operacionais
- documentar padroes de logs, eventos e nomenclatura
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
- Sprint 5 depende da arquitetura mais consolidada e do modelo estrutural de tenant definido
- Sprint 6 depende de direcao clara da camada de dados
- Sprint 8 depende da base operacional e de seguranca estar madura

## Riscos Principais
- Avancar na extracao de servicos sem contratos claros pode deslocar a complexidade em vez de reduzi-la.
- Manter `sqlite3` direto e SQLAlchemy crescendo em paralelo tende a aumentar custo de manutencao e risco de inconsistencias.
- Adiar a definicao estrutural de `tenant` alem da consolidacao de dados pode forcar retrabalho em schema, eventos e autorizacao.
- Tratar o modo `split` local como prova de prontidao produtiva pode mascarar lacunas de retries, observabilidade e operacao distribuida real.
- Evoluir seguranca apenas no fim aumenta a superficie de retrabalho em autenticacao, auditoria e redacao de dados sensiveis.

## Decisoes de Gestao Recomendadas
- Nao aprovar expansao significativa de novas features antes da conclusao das Sprints 1 a 3.
- Exigir contratos documentados para novos fluxos que cruzem limites de servico.
- Considerar a Sprint 4 como marco formal de arquitetura, nao apenas como refatoracao interna.
- Tratar a Sprint 5 como ponto sem retorno para padrao oficial de persistencia.
- Medir sucesso por previsibilidade operacional e capacidade de replicacao, nao apenas por volume de features entregues.

## Indicadores de Sucesso
- tempo de entrada tecnica menor que 30 minutos
- testes executando de forma reprodutivel em CI
- logs estruturados e pesquisaveis
- schema controlado por migracoes
- estado distribuido em producao
- entrada de nova cliente sem fork do projeto

## Fora de Escopo Neste Plano
- mudar regras de atendimento
- reescrever os fluxos de negocio
- alterar catalogo comercial
- mudar comportamento do agente para cliente final

## Resultado Esperado
Ao final desse roadmap, o Chokobot deixa de ser apenas uma automacao funcional para uma loja e passa a ter fundacao tecnica para operar como produto replicavel, com mais seguranca, melhor observabilidade, menor custo de manutencao e caminho claro para escalar.
