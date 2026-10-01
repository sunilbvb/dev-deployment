# 0004. The project is chosen per request, not globally

- Status: Accepted
- Date: 2026-10-01

## Context

Users work on several projects (e.g. a monorepo and a single app). Originally a "switch workspace" call changed one global active project on the server: two browser windows could not show different projects, and switching while a build ran confused logs and history.

## Decision

- Every added project is a tab in the UI. The tab's project is sent as `X-Workspace` with every request.
- The server stores it in a `ContextVar` for that request (`config.set_request_workspace`); all code reads `get_workspace_root()`.
- Job threads are started with a copy of the request context (`jobs._start_in_context`), so a job keeps writing to the project that started it.
- The global default (`WORKSPACE_ROOT`) only decides the first tab shown.

## Consequences

- Multiple tabs/windows work on different projects at once; there is no "switch" step.
- New code must never cache the workspace in module state or start bare threads.
- `/workspace/select` remains for compatibility but the UI does not use it.
