# Proposal: MVP Hardening for Security, Observability, Metrics, and Tests

## 1. Problem Statement
Chokobot is already functional as an MVP, but it still operates with low production hardening. The current codebase shows the following gaps:

- Security-sensitive routes are exposed without a clear authentication/authorization layer for the internal panel.
- The webhook processing path does not have a formal inbound verification, replay protection strategy, or request-level audit trail.
- Observability is based mostly on `print()` statements, which makes troubleshooting, incident response, and trend analysis hard.
- There is no standard metrics surface for latency, throughput, error rates, outbox retries, or AI/tool usage.
- The existing test suite behaves more like manual scripts than automated regression protection.
- The AI layer still has security-sensitive capabilities, especially persistent learnings, without governance.

## 2. Objective
Raise the MVP one level in operational maturity without changing the business logic or the current agent behavior. This initiative will harden the application around five pillars:

1. Security
2. Monitoring
3. Metrics
4. Observability
5. Tests

## 3. Scope

### In Scope
- Add basic but effective security controls around webhook ingestion, internal panel access, secrets handling, and AI persistence surfaces.
- Introduce structured logging, request correlation, and minimal health diagnostics.
- Add an application metrics endpoint and core counters/histograms/gauges.
- Convert the current manual test scripts into automated testable layers with mocks and smoke coverage.
- Define a rollout path that preserves the current MVP logic and current data model.

### Out of Scope
- Rewriting the conversation logic or changing the current business flow.
- Redesigning the SQLite schema.
- Replacing FastAPI, Docker, or the current OpenAI integration.
- Reworking the agent prompts for product behavior improvements beyond security guardrails.

## 4. Guiding Principles
- Do not alter user-facing order flow behavior in this phase.
- Prioritize security and incident visibility over feature breadth.
- Prefer low-risk, incremental hardening steps.
- Keep deployment simple and compatible with the current Docker-based setup.

## 5. Success Criteria
- Internal panel routes are no longer exposed without an authentication layer.
- Webhook requests have configurable inbound verification and structured audit logging.
- The app exposes health and metrics endpoints suitable for uptime checks and dashboards.
- Logs become structured and searchable by request ID, phone hash, route, status, and latency.
- A minimal automated test suite runs locally and in CI without calling external providers.
- Security-sensitive AI surfaces such as persistent learnings are gated, auditable, or disabled by configuration.
