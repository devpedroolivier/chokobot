# Front-end Production Analysis

## Current State

The current back-office UI is fully server-rendered with FastAPI + Jinja templates.

Relevant files:

- `app/templates/painel_principal.html`
- `app/templates/encomendas.html`
- `app/templates/clientes.html`
- `app/api/routes/painel.py`
- `app/api/routes/pedidos.py`
- `app/api/routes/clientes.py`

## Strengths

- Fast delivery: the current panel is direct and operational.
- Low runtime complexity: no frontend build chain today.
- The panel already reflects domain improvements such as `customer_processes`, sync monitoring, and operational kanban.

## Risks Before Production

### 1. The UI layer is tightly coupled to backend templates

Every relevant screen is rendered directly from FastAPI routes. This makes the panel harder to scale when:

- new filters are needed
- realtime refresh is added
- cards become interactive
- stateful workflows grow

### 2. Tailwind is loaded from CDN at runtime

The templates currently use `<script src="https://cdn.tailwindcss.com"></script>`.

That is useful for prototyping, but it is not the right production path because:

- no deterministic CSS build
- no purge/tree-shaking
- no design token governance
- weaker caching and asset control

### 3. There is no reusable component system

The current HTML templates duplicate layout, spacing, table, badge, and navigation patterns.

Examples:

- `app/templates/clientes.html`
- `app/templates/encomendas.html`
- `app/templates/painel_principal.html`

### 4. There is no frontend API contract yet

The current panel consumes Python dicts directly inside Jinja.
That blocks a cleaner migration to a modern frontend runtime unless a stable JSON contract exists.

### 5. Interaction complexity is growing

The panel is moving from simple CRUD to:

- operational kanban
- atendimento vs operação sync
- process ownership
- alerts and monitoring

This is where a React-based frontend begins to pay off.

## Recommendation

Use an incremental migration, not a big-bang rewrite.

### Phase 1

- Keep FastAPI as source of truth.
- Expose JSON snapshot endpoints for the panel.
- Add a separate `frontend/` app with `Next.js + Tailwind CSS`.
- Rebuild the main dashboard first.

### Phase 2

- Move `clientes` and `encomendas` list pages to Next.js.
- Replace full page reload forms with typed actions or API mutations.
- Centralize design tokens and layout components.

### Phase 3

- Add polling or streaming for operational monitoring.
- Add filters, quick actions, and per-process timeline/history.
- Retire Jinja templates after the Next.js admin reaches parity.

## Architecture Decision

Recommended setup:

- FastAPI remains the backend and operational source.
- Next.js becomes the admin/back-office frontend.
- Next.js should consume backend data through server-side fetches or a BFF route.
- Panel credentials must stay server-side, never in browser-exposed env vars.

## What Was Implemented In This Step

- Added `GET /painel/api/snapshot` as the first JSON contract for the dashboard.
- Added a `frontend/` scaffold with `Next.js + Tailwind CSS`.
- The new frontend is prepared to consume the FastAPI panel snapshot without replacing the current Jinja panel yet.

## Go-live Guidance

Do not switch production entirely to the new frontend in one shot.

Safer rollout:

1. Deploy the JSON snapshot endpoint.
2. Deploy the Next.js admin in parallel.
3. Validate parity against the current Jinja panel.
4. Migrate the dashboard first.
5. Migrate CRUD/list pages after operational confidence.
