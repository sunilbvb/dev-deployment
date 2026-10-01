# REST API

The dashboard UI uses this API, and you can script it too. The server listens on `localhost` only (default port `18112`).

## Conventions

| Header | Required | Meaning |
|---|---|---|
| `X-API-Token` | always for `/api/*` | Token from `~/.config/dev-deployment/auth_token.txt` (or `DEPLOYMENT_AUTH_TOKEN`) |
| `X-Workspace` | optional | Absolute path of an added project; without it, the server's default project is used |
| `Content-Type: application/json` | POST | All POST bodies are JSON, except multipart `.p8` upload |

- Requests with a non-localhost `Host` or a foreign `Origin` are rejected (`403`).
- Bodies over 1 MB are rejected (`413`).
- Responses are JSON with `"success": true|false` and `"error"` on failure.

```bash
TOKEN=$(cat ~/.config/dev-deployment/auth_token.txt)
curl -s -H "X-API-Token: $TOKEN" \
     -H "X-Workspace: /Users/me/projects/my-workspace" \
     http://localhost:18112/api/deployment/apps
```

---

## Projects

| Method | Endpoint | Body / query | Returns |
|---|---|---|---|
| GET | `/api/deployment/workspaces` | – | `workspaces` (added projects, each with `isDefault`), `active` (server default), `workspaceMissing` |
| POST | `/api/deployment/workspace/allow` | `{path}` | Adds a project to the list (`config/workspaces_list.json`) |
| POST | `/api/deployment/workspace/remove` | `{path}` | Removes a project from the list (folder untouched); `409` while a build runs there; the startup project cannot be removed |
| GET | `/api/deployment/inspect-path` | `?path=` | `name`, `layout`, `appCount`, `packageCount`, `apps[]` (with `is_package`), `hasMelos`, `isMonorepo` |
| POST | `/api/deployment/pick` | `{kind: "folder"\|"file", prompt?, extensions?}` | Opens the native dialog on the server's desktop → `{path}`, or `{cancelled: true}`, or `{supported: false}` |
| POST | `/api/deployment/workspace/select` | `{path}` | Changes the server's *default* project (the UI does not use this; tabs use `X-Workspace`) |

`inspect-path` only reads added projects and folders chosen through `/pick` in this server session.

## Apps & configuration

| Method | Endpoint | Body / query | Purpose |
|---|---|---|---|
| GET | `/api/deployment/apps` | – | Apps and packages: `id`, `name`, `path`, `stack`, `is_package`, `version`, `color`, `icon` |
| POST | `/api/deployment/apps` (also `/apps/save`) | `{id, name, version?, path}` | Register an app manually |
| POST | `/api/deployment/rescan-workspace` | – | Re-detect apps |
| GET | `/api/deployment/deploy-config` | – | `config.apps.<id>` settings |
| POST | `/api/deployment/deploy-config/save` | full config object | Validate and save settings |
| GET | `/api/deployment/scan-config` | `?app=` | Auto-scan one app (IDs, flavors, Firebase paths) |
| POST | `/api/deployment/scan-all` | `{force?}` | Auto-scan all apps |
| GET | `/api/deployment/templates` | – | Command templates by group |
| GET | `/api/deployment/commands` | `?app=` | Command cards: `id`, `templateId`, `name`, `platform`, `flavor`, `key` (the command line), `configured` |
| POST | `/api/deployment/regenerate` (also `/regenerate-commands`) | – | Re-run discovery for command generation |

## Jobs

| Method | Endpoint | Body / query | Purpose |
|---|---|---|---|
| POST | `/api/deployment/execute` | `{app, templateId, flavor, confirmed?}` | Start a job. The command comes from the app's templates; arbitrary commands are not accepted |
| GET | `/api/deployment/job` | `?id=` | `job.status` (`running`, `success`, `error`, `stopped`), `job.output`, `job.error`, `return_code`, times |
| POST | `/api/deployment/stop` (also `/job/stop`) | `{jobId}` | Stop a job (process group `SIGTERM`, then `SIGKILL`) |
| GET | `/api/deployment/running-jobs` | – | Running jobs across projects |
| GET | `/api/deployment/history` | `?app=&flavor=&status=&limit=` | Finished jobs from `deployment_history.jsonl` |

`execute` responses:

```json
{ "success": true, "jobId": "job_1790857725238", "command": "bash …/run_build.sh uploadAAB gyo_business qa" }
{ "success": false, "needsConfirmation": true, "error": "…" }          // production upload without confirmed:true
{ "success": false, "code": "APP_BUSY", "error": "…" }                  // a job is already running for this app
```

## Credentials

Responses never contain key contents. `app` omitted means *all apps in this project*.

| Method | Endpoint | Body / query | Purpose |
|---|---|---|---|
| GET | `/api/deployment/credentials` | `?app=` | `play` `{path, exists, valid, client_email, source}` and `apple` `{key_id, issuer_id, path, exists, source}`; `source` is `app`, `workspace`, `deploy_config`, `auto` or `env file (…)` |
| POST | `/api/deployment/credentials/scan` | `{folder}` (empty = project root; relative = inside project) | `found[]` with `kind` (`play_service_account`, `apple_p8`, `apple_other_p8`, `firebase_android`, `firebase_ios`), identity fields, `path`, `matches[]` (`{app, flavor}`), `play_hint` |
| POST | `/api/deployment/credentials/import` | `{path, app?, flavor?, issuerId?}` | Import a file from disk |
| POST | `/api/deployment/credentials/upload` | `{filename, contentBase64, app?, flavor?, issuerId?}` | Import uploaded content |
| POST | `/api/deployment/credentials/remove` | `{kind: "play_service_account"\|"apple_p8", app?}` | Forget a key (the file is not deleted) |
| POST | `/api/deployment/p8/upload` | multipart `app_id`, `issuer_id`, `file` — or JSON `{app_id, filename, issuer_id, content_base64}` | Upload an App Store Connect key |

Import rules: files are classified by content; `.p8` keys must be named `AuthKey_<KEYID>.p8`; Issuer IDs must be UUIDs; Firebase files need an `app`.

## Platform

| Method | Endpoint | Query | Purpose |
|---|---|---|---|
| GET | `/api/deployment/ios-cert-check` | `?app=&flavor=` | Certificate and provisioning-profile expiry |
| GET | `/api/deployment/health` | – | Availability of flutter, xcodebuild, fastlane, … |
| GET | `/api/app-icon` | `?url=` | Proxy for app icons shown in the grid |

## Webhook

`POST /api/deployment/webhook` — for CI on the same machine. Authenticated with `WEBHOOK_SECRET` instead of the API token:

- header `X-Webhook-Secret: <secret>`, or
- header `X-Hub-Signature-256: sha256=<HMAC-SHA256 of the body>` (GitHub style).

Body: `{app, templateId, flavor, confirmed?}`. Disabled (`503`) when `WEBHOOK_SECRET` is not set.
