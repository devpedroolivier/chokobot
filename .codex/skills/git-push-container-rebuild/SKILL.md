---
name: git-push-container-rebuild
description: Use when the user wants to prepare Chokobot changes for Git, push them safely, then stop, rebuild, and restart the project containers to validate the updated admin and backend.
---

# Git Push And Container Rebuild

Use this skill when the user asks to:

- review local changes before shipping
- create a commit and push to Git
- stop containers
- rebuild and restart the stack
- confirm the updated services are healthy

## Scope

- Chokobot repo at the current workspace root
- Git status, diff, commit, and push
- Docker Compose rebuild flow for the local stack
- post-rebuild health verification

## Workflow

1. Inspect the worktree first:
   - run `git status --short`
   - separate code changes from runtime artifacts like `dados/`
   - do not include runtime files unless the user explicitly asks
2. Validate before shipping:
   - run the smallest relevant backend/frontend checks for the current change set
   - report blockers before committing
3. Prepare the commit:
   - stage only intended files
   - use a direct, descriptive commit message
   - never rewrite unrelated user changes
4. Push:
   - confirm branch state
   - push to the configured remote
5. Rebuild containers:
   - stop the stack with Docker Compose
   - rebuild and restart in detached mode
   - check `docker compose ps`
   - if needed, inspect recent logs for unhealthy services
6. Report:
   - commit hash
   - push target
   - container health
   - service URLs or exposed ports when visible

## Project Rules

- Preserve `dados/atendimentos.txt`, `dados/chokobot.db`, and `dados/domain_events.jsonl` unless the user explicitly wants them committed.
- Prefer non-interactive Git commands only.
- Do not use destructive Git cleanup.
- If Docker or Git commands require elevated permissions, request escalation directly through the tool flow.

## Typical Commands

- `git status --short`
- `git add <files>`
- `git commit -m "<message>"`
- `git push origin <branch>`
- `docker compose down`
- `docker compose up --build -d`
- `docker compose ps`

## Validation

Use only what fits the current change set, then finish with container checks:

- backend tests or `python3 -m compileall app tests`
- frontend build if admin code changed
- `docker compose ps`

## Output Expectations

When using this skill, report:

- what was committed and what was intentionally left out
- the commit hash
- whether push succeeded
- whether rebuild succeeded
- current container health
