# CLAUDE.md — Instructions for AI coding agents

Read this before changing code. Humans: the same rules are in [CONTRIBUTING.md](CONTRIBUTING.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

## What this is

A localhost web console that builds, uploads and releases mobile apps for **any** project layout. Backend: Python ≥ 3.10 standard library (`features/deployment/backend/`). Frontend: vanilla JS (`features/deployment/frontend/`). Work is done by Bash scripts and a Dart release tool (`features/deployment/scripts/`).

## Commands

```bash
./start.sh                                                     # run (needs Python >= 3.10)
python3 -m unittest discover -s tests                          # all tests
dart analyze features/deployment/scripts/release_changelog_tagger.dart
for f in $(find features/deployment/scripts -name "*.sh"); do bash -n "$f"; done
```

On macOS the system `python3` is 3.9 — use `/opt/homebrew/bin/python3.12` (or similar).
Some tests write to `config/workspaces_list.json`; restore it after the suite.

## Rules (do not break)

1. **Generic only.** Never hardcode `apps/<name>`, `packages/`, app IDs, package names or key file names. Use `_resolve_app_dir` / `_discover_apps_in_workspace` (Python) and `resolveAppDir`, `resolveAndroidPackageName`, `resolvePlayServiceAccount` (Bash). Every layout in the README detection table must keep working.
2. **Per-request project.** Read the project with `config.get_workspace_root()`. Start background threads with `jobs._start_in_context(...)`, never bare `threading.Thread`.
3. **No secrets in projects or API responses.** Key handling goes through `credentials.py` only.
4. **Only template commands run.** Never execute command text taken from a request.
5. **Visible operations.** State-changing steps (git, uploads) log what they run and fail the job on error.
6. **Standard library only** in Python. No new dependencies, no database.
7. **UI** uses `developer-dashboard-ui` classes; the kit loads from a CDN, so local CSS fixes go into `features/deployment/frontend/styles.css`. Wrap `sessionStorage`/`localStorage` in `try/catch`.

## Where things are

| Need | Look in |
|---|---|
| Project/app detection, layouts, flavors | `backend/config.py` |
| Command cards, script vs direct, locking | `backend/commands.py`, `config/deployment_templates.json` |
| Running jobs, logs, history, auto-release | `backend/jobs.py` |
| Keys | `backend/credentials.py` |
| Routes, auth | `backend/server.py` |
| Build/upload logic | `scripts/json_utils.sh`, `scripts/android/`, `scripts/ios/` |
| Releases | `scripts/release_changelog_tagger.dart` |
| Planned features | `docs/proposals/` |
| Why things are as they are | `docs/adr/` |

## Testing changes

- Add a unit test for every fix (helpers `_flutter_app`, `_flutter_package` in `tests/test_deployment.py`).
- Credential tests must patch `credentials.CONFIG_DIR`, `KEYS_DIR`, `STORE_FILE`, `APPLE_KEYS_DIR` to temp folders.
- UI changes: verify in a browser, not only with tests.
- Never upload to stores or push to real remotes while testing; use a local bare repository as `origin`.

## Docs

Update README / FAQ / ARCHITECTURE / docs/API.md and add a CHANGELOG entry under *Unreleased* whenever behaviour changes.
