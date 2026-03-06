# Implementation Tasks: MVP Hardening

## Phase 1: Security First
- [ ] 1.1 Add authentication for `/painel` and related internal routes.
- [ ] 1.2 Define and implement webhook inbound verification strategy.
- [ ] 1.3 Add replay protection policy for webhook processing.
- [ ] 1.4 Gate `save_learning` behind configuration and add audit logs.
- [ ] 1.5 Redact/hash phone numbers and sensitive payload fields in logs.
- [ ] 1.6 Move hardcoded admin controls to environment-driven configuration.

## Phase 2: Observability
- [ ] 2.1 Introduce structured logging for HTTP, webhook, AI, provider, and DB events.
- [ ] 2.2 Add request ID middleware and propagate correlation IDs.
- [ ] 2.3 Standardize error logging and event naming.
- [ ] 2.4 Add a minimal operational log policy for success, warning, and security events.

## Phase 3: Metrics and Monitoring
- [ ] 3.1 Add `/healthz` liveness endpoint.
- [ ] 3.2 Add `/readyz` readiness endpoint.
- [ ] 3.3 Add `/metrics` endpoint.
- [ ] 3.4 Instrument HTTP latency, webhook counters, AI latency, and outbox retry metrics.
- [ ] 3.5 Add Docker healthcheck and align compose/runtime configuration.
- [ ] 3.6 Document minimum dashboards and alert thresholds.

## Phase 4: Tests
- [ ] 4.1 Convert current script-style tests into proper pytest test cases with assertions.
- [ ] 4.2 Add unit tests for menu filtering and security helpers.
- [ ] 4.3 Add FastAPI integration tests with dependency mocking.
- [ ] 4.4 Add AI runner tests using mocked OpenAI responses.
- [ ] 4.5 Add smoke tests for container startup and core endpoints.

## Phase 5: Delivery Readiness
- [ ] 5.1 Validate hardening changes without altering current MVP behavior.
- [ ] 5.2 Rebuild and verify Docker container locally.
- [ ] 5.3 Update deployment and environment documentation.
- [ ] 5.4 Define follow-up backlog for agent improvements after hardening is complete.
