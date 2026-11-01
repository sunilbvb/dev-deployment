# 0004. MCP server — drive builds in plain English

- **Status:** Prototype built (read + run tools); follow-ups in §5
- **Related:** `features/mcp/` (Dart package: `bin/server.dart`, `lib/`, `test/`), [docs/API.md](../API.md)

## 1. Summary

An MCP server (stdio) lets an AI client (Claude Desktop, Claude Code, …) list apps, run builds/uploads, watch jobs and read history from plain-English requests. The model does the language work; the server only exposes fixed tools.

## 2. Design

- **Thin bridge** over the existing REST API. No new backend logic.
- **Dart**, built on the official [`dart_mcp`](https://pub.dev/packages/dart_mcp) package (stdio transport, schema validation). It is a separate package under `features/mcp/`, so the Python backend stays standard-library only (rule 6). `dart compile exe` gives a single binary.
- **Rule 4:** `run_command` forwards only `app`, `templateId`, `flavor`, `confirmed`, `releaseNotes`. Extra fields are dropped; the console validates the template.
- **Rule 2:** every tool takes an optional `workspace`, sent as `X-Workspace`. No server-side "current project".
- **Rule 3:** the token is read from `~/.config/dev-deployment/auth_token.txt` (or `DEPLOYMENT_AUTH_TOKEN`) and never returned.
- **Safety:** tools carry `readOnlyHint`/`destructiveHint`. PROD store deploys are refused by the console unless `confirmed: true`; the tool text tells the model to set it only after the user approves.
- **Long jobs:** `run_command` returns a job id at once; the model polls `get_job` (log tail capped at 8000 chars).

## 3. Tools

`list_projects`, `list_apps`, `list_commands`, `run_command`, `get_job`, `stop_job`, `running_jobs`, `history`, `doctor`.

## 4. Use

Start the console (`./start.sh`), then register the server, e.g. Claude Code:

```bash
cd features/mcp && dart pub get
claude mcp add dev-deployment -- dart run /path/to/dev-deployment-repo/features/mcp/bin/server.dart
# or a native binary:
dart compile exe bin/server.dart -o dev-deployment-mcp
```

## 5. Pending

- Release-notes, version-bump and pipeline tools (`pipelines/run`).
- Log secret filtering audit (confirm job logs never contain keys).
- Optional auto-start of the console when unreachable.
- Verify against Claude Desktop config and a real (non-store) build end to end.
