---
name: nextjs-bundle-guard
description: Use when improving performance of the Chokobot Next.js frontend, especially bundle size, server versus client boundaries, route payloads, unnecessary hydration, heavy table screens, dynamic imports, and production build regressions.
---

# Next.js Bundle Guard

Use this skill for frontend performance work in `frontend/` when the issue is page weight, excessive client-side code, slow builds, unnecessary hydration, or avoidable runtime cost in the admin.

## Focus Areas

- `frontend/src/app/`
- `frontend/src/components/`
- `frontend/src/lib/`
- `frontend/package.json`
- `frontend/next.config.mjs`
- `frontend/src/app/globals.css`

## Typical Problems

- server components promoted to client components without need
- large tables or dashboards holding too much client state
- repeated fetches for the same route data
- heavy libraries imported on initial load
- snapshot payloads larger than the page really needs
- forms/actions loading more JS than necessary
- images, fonts, and visual polish hurting route performance

## Workflow

1. Start from the route under pressure:
   - `/`
   - `/operacoes`
   - `/clientes`
   - `/encomendas`

2. Check these in order:
   - does the page really need `"use client"`?
   - can filtering/sorting stay server-side or be reduced?
   - are heavy components split from the first paint?
   - are fetches duplicated across layout/page/component layers?
   - is the route consuming more snapshot data than it renders?
   - are imports that should be dynamic or server-only?

3. Prefer these fixes:
   - move logic back to server components
   - narrow props and payload shapes
   - isolate interactive islands instead of hydrating whole pages
   - lazy-load expensive components only when opened
   - keep tables and cards cheap to render

4. Only optimize visuals after the route structure is efficient.

## Project Rules

- Preserve the current admin UX and visual language while optimizing.
- Do not add client memoization everywhere by reflex.
- Prefer simpler component boundaries over premature micro-optimization.
- Avoid adding dependencies unless the gain is clear and measurable.

## Validation

Primary check:

- `cd frontend && npm run build`

Also inspect:

- whether a route became server-rendered instead of over-hydrated
- whether a large client component was split into smaller interactive islands
- whether payload requirements shrank for the consuming page

## Output Expectations

When using this skill, report:

- which route or component path was optimized
- whether the gain came from bundle reduction, hydration reduction, or payload reduction
- what build or validation ran
- any remaining front-end performance risk
