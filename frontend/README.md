# Frontend

This folder contains the new admin frontend scaffold using `Next.js + Tailwind CSS`.

## Environment

Server-side environment variables expected by the dashboard:

- `PANEL_BACKEND_URL`
- `ADMIN_SESSION_SECRET`

Example:

```bash
PANEL_BACKEND_URL=http://localhost:8000
ADMIN_SESSION_SECRET=troque-essa-chave
```

You can bootstrap it from the example file:

```bash
cp frontend/.env.local.example frontend/.env.local
```

The login screen uses the same FastAPI panel credentials and stores them in an encrypted
HTTP-only session cookie inside the Next.js app. `PANEL_AUTH_USERNAME` and
`PANEL_AUTH_PASSWORD` can still be used as a server-side fallback, but the intended flow is
session-based access through `/login`.

## Commands

```bash
npm install
npm run dev
```

## Docker

The project root `docker-compose.yml` can now publish the admin frontend as a dedicated
service on port `3000`.

Important variables for containerized deployment:

- `ADMIN_SESSION_SECRET`
- `ADMIN_FRONTEND_URL` on the FastAPI side, pointing to the public admin URL
- `PANEL_AUTH_ENABLED=1`
- `PANEL_AUTH_USERNAME`
- `PANEL_AUTH_PASSWORD`

## Current Scope

- consumes `GET /painel/api/snapshot`
- renders sync metrics, alerts, process sections, WhatsApp cards, and the operational kanban
- now includes login/logout and protected admin routes
- can start replacing Jinja routes when `ADMIN_FRONTEND_URL` is configured in the FastAPI app
