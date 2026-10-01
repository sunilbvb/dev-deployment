# 0001. Backend uses the Python standard library only, no database

- Status: Accepted
- Date: 2026-10-01

## Context

The console runs on each developer's own machine next to Flutter, Xcode and the Android SDK. Anything it needs must install with zero friction: no virtualenv, no package manager, no services to keep running. Its data is small — a list of apps, settings, a job history.

## Decision

- The backend uses only the Python standard library (`http.server`, `subprocess`, `json`, `pathlib`, `contextvars`, `email.parser`). Python ≥ 3.10.
- There is no database. State is plain JSON / JSONL files: per project in `<project>/.dev-dashboard/`, per user in `~/.config/dev-deployment/`.
- The frontend is vanilla HTML/JS with the shared `developer-dashboard-ui` CSS kit; no build step.

## Consequences

- `./start.sh` works on any machine with Python 3.10+; nothing to install or migrate.
- Settings are human-readable and can be reviewed or committed.
- We write some code a framework would give us (routing, multipart parsing, auth checks) and must keep it secure ourselves — see the security tests.
- Concurrency is simple threads; fine for one user, not meant for a shared server.
