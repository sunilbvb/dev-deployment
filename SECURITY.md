# Security Policy

The Dev Deployment Console runs build commands and handles signing / store-upload keys, so security reports are taken seriously.

## Reporting a vulnerability

**Please do not open a public issue.** Report privately through GitHub: **Security → Report a vulnerability** on this repository (private vulnerability reporting). Include:

- what an attacker can do, and under which conditions,
- steps to reproduce (version / commit, OS, request or file used),
- any suggested fix.

You can expect a first reply within 7 days. Fixes are released on `develop` and noted in [CHANGELOG.md](CHANGELOG.md); reporters are credited unless they prefer otherwise.

## Supported versions

Only the latest `develop` branch receives security fixes.

## Security model

The console is a **single-user tool for your own machine**. It is safe under these assumptions — please report anything that breaks them:

| Protection | How |
|---|---|
| Localhost only | Requests with a non-localhost `Host` (DNS rebinding) or a foreign `Origin` are rejected |
| Authenticated API | Every `/api/*` request needs `X-API-Token`; the token is generated per user (`~/.config/dev-deployment/auth_token.txt`, `chmod 600`) |
| No arbitrary commands | `/execute` selects commands from templates; request bodies cannot supply command text |
| Shell safety | Values put into command lines are validated (`^[A-Za-z0-9._-]+$`) and quoted |
| Folder access | Only added projects and folders the user chose in the native dialog can be inspected |
| Secrets outside projects | Keys are stored in `~/.config/dev-deployment/` and `~/.appstoreconnect/private_keys/` with `chmod 600`; APIs never return key contents ([ADR 0002](docs/adr/0002-credentials-outside-the-project.md)) |
| Webhook | Disabled unless `WEBHOOK_SECRET` is set; requires the secret or an HMAC-SHA256 signature |
| Limits | Request bodies ≤ 1 MB; imported key files ≤ 1 MB |

**Out of scope / not supported:** exposing the port to a network or the internet (`0.0.0.0`, tunnels such as ngrok), multi-user servers, and attackers who already have access to your user account.

## For users

- Keep the server on `localhost`.
- Do not commit `private_keys/`, `.env` or downloaded key files; use **Configure → Keys** to import them.
- Treat the API token like a password.
- If your team commits `.dev-dashboard/deploy_config.json`, review changes to it like code changes.
