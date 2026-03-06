# Technical Design: MVP Hardening Layer

## 1. Architecture Overview
This initiative adds an operational hardening layer around the current MVP. The goal is not to rewrite the application core, but to wrap it with better controls, telemetry, and testability.

The hardening layer is organized into four implementation tracks:

1. Security Controls
2. Observability and Logging
3. Metrics and Monitoring
4. Automated Test Coverage

## 2. Current Risk Summary

### Security
- Internal HTML panel routes are exposed without auth.
- Webhook processing lacks formal inbound verification.
- Admin behavior is partially hardcoded.
- Sensitive integrations are loaded at import time.
- AI persistent learnings can be written without governance.

### Observability
- Logging is mostly `print()` based.
- There is no request correlation or phone redaction policy.
- No clear split between business events, errors, and infrastructure events.

### Metrics and Monitoring
- No health endpoint.
- No readiness diagnostics.
- No Prometheus-style metrics.
- No counters for webhook throughput, AI latency, or outbox retries.

### Testing
- Existing files under `tests/` are mostly scripts with `print()` and live-provider dependencies.
- There is no reliable regression suite for critical flows.

## 3. Proposed Components

### A. Security Layer

#### A1. Internal Panel Protection
- Add middleware or route dependency for panel authentication.
- Start with simple, environment-configured credentials or token-based access to avoid a large auth project.
- Add CSRF protection strategy for form-based mutations.

#### A2. Webhook Verification
- Add configurable inbound verification using one of:
  - shared secret header
  - HMAC signature
  - provider allowlist/IP guard if signature is unavailable
- Add basic replay protection for webhook events using message ID plus a bounded time window.

#### A3. AI Guardrails
- Gate `save_learning` behind environment configuration.
- Add audit logging when the AI attempts a persistent write.
- Consider disabling persistent learnings by default in production until reviewed.

#### A4. Secret and Data Hygiene
- Stop leaking provider responses and raw customer content in logs where unnecessary.
- Redact or hash phone numbers in structured logs.
- Ensure secrets are only read from environment and never echoed back.

### B. Observability Layer

#### B1. Structured Logging
- Replace ad hoc `print()` with standard structured application logging.
- Include fields such as:
  - request_id
  - route
  - method
  - status_code
  - latency_ms
  - phone_hash
  - event_type
  - provider
  - ai_agent

#### B2. Request Correlation
- Inject a request ID for every inbound HTTP request.
- Propagate that request ID into webhook processing, outbound provider calls, and error logs.

#### B3. Error Taxonomy
- Standardize error events into:
  - validation errors
  - provider errors
  - AI/tool errors
  - database errors
  - security events

### C. Metrics Layer

#### C1. Health Endpoints
- `/healthz`: liveness
- `/readyz`: readiness with basic dependency checks

#### C2. Metrics Endpoint
- `/metrics` in Prometheus format

#### C3. Core Metrics
- HTTP request count and latency by route/method/status
- Webhook accepted/ignored/error counters
- AI completion latency and tool call counters
- Outbox enqueue count and retry count
- Delivery/status update counters
- Security counters:
  - unauthorized panel access attempts
  - invalid webhook signature attempts
  - disabled AI write attempts

### D. Test Strategy

#### D1. Unit Tests
- Pure tests for menu filtering, repository behavior, payload normalization, and price helpers.

#### D2. Integration Tests
- FastAPI route tests for:
  - webhook accepted/ignored/error paths
  - panel auth behavior
  - metrics and health endpoints

#### D3. AI Boundary Tests
- Replace live OpenAI dependency with mocks/fakes at the runner boundary.
- Assert tool routing behavior and failure handling, not model creativity.

#### D4. Smoke Tests
- Keep a minimal smoke path for container startup and one basic end-to-end mocked conversation.

## 4. Rollout Strategy

### Phase 1
- Security controls that do not alter business logic:
  - panel auth
  - webhook verification
  - AI learning gate

### Phase 2
- Structured logging and request correlation
- Health and metrics endpoints

### Phase 3
- Automated tests with mocks
- CI-friendly smoke coverage

### Phase 4
- Optional operational integrations:
  - uptime checks
  - dashboards
  - alert rules

## 5. Operational Recommendations
- Keep SQLite for now, but monitor lock/error rate.
- Do not introduce distributed tracing yet; structured logs plus metrics are sufficient for this stage.
- Keep the current Docker flow, but add container-level health checks once app endpoints exist.

## 6. Acceptance Boundaries
- No change to menu/business decision logic.
- No change to order persistence contract.
- No change to current MVP routing intent.
- Any AI hardening must focus on safety and auditability, not on altering product behavior.
