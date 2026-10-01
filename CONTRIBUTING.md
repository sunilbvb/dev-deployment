# Contributing to Dev Deployment Console 🚀

Thanks for helping! Bug fixes, features, docs and UI polish are all welcome.

---

## 📑 Table of Contents

1. [Getting Started](#-getting-started)
2. [Architecture in One Minute](#️-architecture-in-one-minute)
3. [Development Setup](#️-development-setup)
4. [Testing](#-testing)
5. [Pull Requests](#-pull-requests)
6. [Code Standards](#-code-standards)
7. [Roadmap](#️-roadmap)

---

## 🏁 Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/dev-deployment.git
cd dev-deployment
git checkout develop
```

Open an issue before large changes so we can agree on the approach. Designed features waiting for a builder are in [docs/proposals/](docs/proposals/). Security issues: see [SECURITY.md](SECURITY.md), not public issues.

---

## 🏗️ Architecture in One Minute

- **Backend** (`features/deployment/backend/`): Python ≥ 3.10, standard library only. `server.py` (HTTP, auth, routing) → `router.py` (facade) → `config.py` (discovery), `commands.py` (command cards), `jobs.py` (processes, logs, history), `credentials.py` (keys), `picker.py` (native dialogs), `p8.py`.
- **Frontend** (`features/deployment/frontend/`): vanilla HTML/JS on the `developer-dashboard-ui` kit — `app.js` (home screen, projects, jobs), `setup.js` (Configure dialog).
- **Scripts** (`features/deployment/scripts/`): Bash build/upload layer called via `run_build.sh`, plus `release_changelog_tagger.dart` for releases.

Design rules that every change must keep:

1. **Generic, not project-specific.** Never hardcode `apps/<name>`, `packages/`, file names or app IDs. Use `resolveAppDir`, `resolveAndroidPackageName`, `resolvePlayServiceAccount` (scripts) and `_resolve_app_dir`, `_discover_apps_in_workspace` (backend). Every layout in the README's detection table must keep working.
2. **Per-request project.** The UI sends `X-Workspace` on every request. Backend code must use `get_workspace_root()` (never the module-level default) and start background threads with `jobs._start_in_context`.
3. **No secrets in projects.** Keys go through `credentials.py` into the user's private folders; project files hold identifiers and paths only.
4. **Visible operations.** Commands that change state (git, uploads) must log what they run and fail the job on errors.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how it works and every file, and [docs/adr/](docs/adr/) for the decisions behind it.

---

## 🛠️ Development Setup

```bash
cp .env.example .env              # optional
./start.sh                        # needs Python >= 3.10
```

Open `http://localhost:18112`. HTML/JS/CSS changes apply on page reload; Python changes need a server restart.

A realistic playground: create a folder with two `flutter create` apps and a `flutter create --template=package` package, `git init` it, add it with **+ Import Project**. To test releases without touching GitHub, add a local bare repository as `origin` (`git init --bare /tmp/test-remote.git`).

---

## 🧪 Testing

```bash
python3 -m unittest discover -s tests
dart analyze features/deployment/scripts/release_changelog_tagger.dart
for f in $(find features/deployment/scripts -name "*.sh"); do bash -n "$f"; done
```

- Add a test for every bug fix and every new layout or credential case (`tests/test_deployment.py` has helpers `_flutter_app` and `_flutter_package`).
- Tests must not touch real user data: credential tests patch `credentials.CONFIG_DIR`, `KEYS_DIR`, `STORE_FILE` and `APPLE_KEYS_DIR` to temp folders.
- Known issue: some existing tests still write to `config/workspaces_list.json`; restore it after running the suite.
- For UI changes, use the feature in a browser, not just the tests.

---

## 📤 Pull Requests

1. Branch from `develop`: `git checkout -b feat/short-name`.
2. Use [Conventional Commits](https://www.conventionalcommits.org) — the release tool builds changelogs from them:
   - `feat(credentials): scan folders for Play keys`
   - `fix(release): fail the job when git push fails`
   - `docs(readme): document project tabs`
3. Run the tests above; update README / FAQ / ARCHITECTURE / docs/API.md when behaviour changes and add an entry under *Unreleased* in [CHANGELOG.md](CHANGELOG.md).
4. Open the PR against `develop`.

---

## 🎨 Code Standards

### UI

- Use the [`developer-dashboard-ui`](https://github.com/sunilbvb/developer-dashboard-ui) classes (`.ui-card`, `.ui-field`, `.ui-input`, `.ui-button[data-variant]`, `.ui-badge`, `.ui-modal`, `.ui-dropzone`, `.ui-segmented-control`) and its CSS variables. Keep dashboard-specific CSS small and in `features/deployment/frontend/styles.css`.
- The kit loads from the CDN; a fix in `frontend/css/developer-dashboard-ui-kit.css` only affects the local fallback, so also add it to `styles.css` or the kit repository.
- Wrap `sessionStorage` / `localStorage` access in `try/catch`.

### Python

- Standard library only (no `requests`, `flask`, …); Python ≥ 3.10 syntax.
- Validate IDs with `SAFE_ID_PATTERN`; quote shell arguments with `shlex.quote`.
- Never return secret contents from an API.

### Bash

- `set -euo pipefail` style, quote variables, pass `bash -n` and shellcheck.
- Resolve paths through the helpers in `json_utils.sh`.

---

## 🗺️ Roadmap

Done recently: generic discovery for all layouts, project tabs, native folder picker, credential scanning/import, release logging, Melos fallback to direct builds.

Open — pick one:

- [ ] **Pipelines** — chain existing commands into a saved per-app workflow. Fully designed and split into tasks: **[docs/proposals/0001-pipelines.md](docs/proposals/0001-pipelines.md)** — the best place to start.
- [ ] **Editable release notes** — review and edit the generated summary between Preview and Tag.
- [ ] **Test isolation** — make all tests use a temporary `config/` folder.
- [ ] **Remove unused leftovers** — `frontend/modules/*.js`, `config/workspace_config.json`.
- [ ] **Slack / Discord / Teams** notification cards next to Google Chat.
- [ ] **Terminal search** and **build-time charts** in History.
- [ ] **Dynamic Gradle flavors** read via Gradle instead of static parsing.
