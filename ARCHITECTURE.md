# Architecture

How the Dev Deployment Console is built, the rules every change must keep, and a map of every file. For using the tool see the [README](README.md); for the HTTP API see [docs/API.md](docs/API.md); for the reasons behind key decisions see [docs/adr/](docs/adr/).

---

## 📑 Contents

1. [The Big Picture](#-the-big-picture)
2. [Request Flow](#-request-flow)
3. [How a Job Runs](#️-how-a-job-runs)
4. [Project Discovery](#-project-discovery)
5. [Credentials](#-credentials)
6. [Releases](#️-releases)
7. [Universal Webhooks & Notifications](#-universal-webhooks--notifications)
8. [Visual Pipeline Engine](#-visual-pipeline-engine)
9. [Diagnostics, Sentinels & Artifact Hosting](#-diagnostics-sentinels--artifact-hosting)
10. [Server Lifecycle Management](#-server-lifecycle-management)
11. [Design Rules](#-design-rules)
12. [File Map](#️-file-map)

---

## 🧭 The Big Picture

```text
┌──────────────── Browser tab ────────────────┐
│ index.html · app.js · setup.js              │   one project per tab
└──────────────────────┬──────────────────────┘
                       │ HTTP  (X-API-Token, X-Workspace)
┌──────────────────────▼──────────────────────┐
│ server.py   auth · host/origin checks ·     │
│             routing · static files          │
│ router.py   facade                          │
│ ├ config.py       discovery & settings      │
│ ├ commands.py     command cards             │
│ ├ jobs.py         processes & history       │
│ ├ credentials.py  keys                      │
│ └ picker.py       native dialogs            │
└──────────────────────┬──────────────────────┘
                       │ subprocess (+ credential env vars)
┌──────────────────────▼──────────────────────┐
│ scripts/run_build.sh → json_utils.sh,       │
│ android/, ios/, chat/,                      │
│ release_changelog_tagger.dart               │
└──────────────────────┬──────────────────────┘
                       ▼
        flutter · xcodebuild · fastlane · melos · git
```

Three layers, each replaceable on its own:

| Layer | Language | Responsibility |
|---|---|---|
| **UI** | HTML + vanilla JS | Show projects, apps and commands; start/stop jobs; stream logs; Configure dialog |
| **Backend** | Python ≥ 3.10, standard library only | Understand projects, build command lines, run jobs, keep history, manage keys |
| **Scripts** | Bash + Dart | Do the actual build/upload/release work with the platform tools |

There is no database. State lives in JSON files: per project in `<project>/.dev-dashboard/`, per user in `~/.config/dev-deployment/`.

---

## 🔁 Request Flow

1. `index.html` is served with the auth token injected (`window.__DEPLOYMENT_TOKEN__`).
2. `app.js` wraps `fetch`: every request gets `X-API-Token` and `X-Workspace` (the project of this browser tab).
3. `server.py` rejects non-localhost `Host` / foreign `Origin`, checks the token, and — if `X-Workspace` is an added project — sets it for this request (`config.set_request_workspace`, a `ContextVar`).
4. Every backend function calls `get_workspace_root()`, which returns the request's project. Two tabs can therefore work on two projects at once without a global switch.

---

## ⚙️ How a Job Runs

```text
POST /execute {app, templateId, flavor}
  → commands.get_commands(app)          find the card; never run posted command text
  → jobs.execute_command
      ├ production upload?  → needs confirmed: true
      ├ app busy?           → APP_BUSY
      ├ env = os.environ + WORKSPACE_ROOT, DEPLOYMENT_PYTHON,
      │       credentials.job_env(app)  (SERVICE_ACCOUNT_JSON, APPLE_API_KEY, …)
      ├ subprocess in the project root (own process group)
      └ threads started with the request context:
            stream stdout/stderr → job.output / job.error
            finish → history entry → optional chained release
GET /job?id=   → UI polls and appends new output to the Live Terminal
```

Commands are generated from `config/deployment_templates.json`:

- Templates in `commands.ACTION_MAP` run as `bash scripts/run_build.sh <function> <app> <flavor>` (build/upload/deploy, all release actions).
- All other templates run their `command_template` directly in the app folder.
- In the script layer, Melos workspaces use a matching Melos script when the root `pubspec.yaml` defines one (`runMelosOrDirect`), otherwise the same step runs directly.

---

## 🔍 Project Discovery

`config._discover_apps_in_workspace(root)`:

1. Read members from `melos.yaml` `packages:` / root `pubspec.yaml` `workspace:` if present (only folders with a manifest; `ignore:` applies).
2. Otherwise walk the tree (depth ≤ 4): every folder with `pubspec.yaml` / `package.json` is a project; inside a project, platform/source folders are skipped; `example/`, `build/`, hidden folders are skipped everywhere.
3. Include the root itself when it is a project (not a pure workspace aggregator).
4. Classify with `_detect_app_in_dir`: app if `android/`, `ios/` or `lib/main*.dart`, and not a Flutter plugin; otherwise package.
5. IDs = folder names; duplicates get a parent-folder suffix.

`_describe_layout` turns the result into the label shown in Import Project. `_resolve_app_dir(app_id)` maps an ID back to its folder and is used by the backend and, through `resolveAppDir`, by every script.

---

## 🔑 Credentials

`credentials.py` owns all key handling:

- **Scan** — walk a folder, classify files by content (`_classify_bytes`), match Firebase files to apps by package/bundle ID.
- **Import** — copy Play keys to `~/.config/dev-deployment/keys/`, `.p8` keys to `~/.appstoreconnect/private_keys/` (`chmod 600`); record the mapping in `~/.config/dev-deployment/credentials.json` keyed by project path, with an app scope and a workspace-wide scope.
- **Resolve** — `_effective(app)` merges app over workspace values, then legacy `deploy_config` paths and conventional locations.
- **Use** — `job_env(app)` produces the environment variables for jobs; `get_credentials_status(app)` feeds the UI (never returns key contents).

The scripts honour those variables first and keep their own fallbacks (`resolvePlayServiceAccount`, Apple key paths), so older setups still work.

---

## 🏷️ Releases

`release_changelog_tagger.dart` (run via `run_build.sh release*`):

1. Discover packages in any layout (`scanWorkspacePackages`), find the target and its internal dependencies.
2. Find the previous tag `<app>-v<version>` and collect commits since then; attribute each commit with `isInPackage` (exact path ownership, nested packages win).
3. Print the commit table, compile the changelog, update `CHANGELOG.md` / version.
4. Commit and create an annotated tag (`--cleanup=verbatim` keeps headings); push to `origin`.
5. Every mutating git command is echoed with its output (`runGit`); push failures fail the job; a final summary is printed.

---

## 🔔 Universal Webhooks & Notifications

`notifications.py` provides a decoupled, multi-channel notification engine and an incoming CI/CD ingestion gateway:

1. **Multi-Destination Outgoing Webhooks**:
   - Out-of-the-box support for **Slack**, **Discord**, **Microsoft Teams**, **Google Chat**, and **WhatsApp** (Meta Cloud API & Twilio REST API).
   - Deliveries run asynchronously in daemon threads upon job completion or failure, capturing HTTP status codes and response bodies without blocking builds.
2. **Dynamic Template & Custom Header Engine**:
   - Custom payload templates with automatic variable interpolation: `{app}`, `{status}`, `{flavor}`, `{version}`, `{commit}`, `{author}`, `{summary}`, `{run_id}`, `{download_url}`, `{timestamp}`.
   - User-defined HTTP headers for custom enterprise webhook gateways (e.g. `Authorization: Bearer <token>`, `X-Custom-Header: value`).
3. **Incoming CI/CD Ingestion Gateway**:
   - Generic endpoint `/api/deployment/webhook/incoming` and provider-specific `/api/deployment/webhook/incoming/<provider>`.
   - Ingests triggers from **GitHub Actions**, **GitLab CI/CD**, **Slack Slash Commands**, and **cURL**.
   - Cryptographic signature and token verification: HMAC SHA-256 (`X-Hub-Signature-256`), GitLab secret token (`X-Gitlab-Token`), Slack request signature (`X-Slack-Signature`), and Bearer secret (`X-Webhook-Secret`).
   - Automatically maps incoming events (`push`, `tag`, `slash_command`) to trigger configured deployment pipelines or commands.

---

## 🔀 Visual Pipeline Engine

`pipelines.py` implements chained, multi-step deployment sequences with fine-grained control:

1. **Pipeline Model & Storage**:
   - Persisted in `<project>/.dev-dashboard/pipelines.json` per workspace.
   - Defines ordered step sequences: Pre-flight Diagnostics → Clean → Build → Quality Checks → Deploy/Upload → Custom Shell Steps.
2. **Visual Builder & Categorized Picker**:
   - Web UI enables non-terminal pipeline construction with categorized step picker (`Diagnostics`, `Builds`, `Uploads`, `Quality/Test`, `Custom Shell`).
   - Interactive step reordering (move up/down) with per-step deletion and continue-on-failure settings.
3. **Custom Shell Execution**:
   - Custom shell steps execute within the project workspace context, receiving job environment variables and timeout enforcement.
4. **Execution Engine & Fail-Safe Controls**:
   - Steps execute sequentially; step failure halts execution immediately unless `continue_on_failure: true` is configured for non-critical steps (e.g., test reports).
   - Live execution tracking in the dashboard terminal with per-step status badges (`pending`, `running`, `passed`, `failed`).

---

## 🩺 Diagnostics, Sentinels & Artifact Hosting

Pre-flight verification, health monitoring, and zero-cable installation:

1. **App Doctor (`doctor.py`)**:
   - One-click pre-flight diagnostic suite inspecting Flutter SDK, Android SDK/NDK, Java/JDK, CocoaPods, Xcode, Fastlane, Melos, Git clean working tree, and Firebase configs.
   - Categorizes findings into `PASS`, `WARN`, and `FAIL` with actionable remediation commands.
2. **Expiry Sentinels (`sentinel.py`)**:
   - Background and on-demand inspection of Apple distribution certificates, `.p8` API keys, and Android Keystores (`keytool`).
   - Flags credentials expiring within 30 days and alerts when cross-platform Firebase project IDs differ between Android (`google-services.json`) and iOS (`GoogleService-Info.plist`).
3. **Local Artifact Hosting & Wireless QR Scanning (`artifacts.py`, `qr.py`)**:
   - Discovers built `.apk`, `.aab`, and `.ipa` artifacts and serves them over local HTTP (`/api/deployment/download/<job_id>`).
   - Generates pure Python QR codes (SVG/PNG matrix builder, zero external pip libraries) displayed in terminal and web UI for direct Wi-Fi scan-to-install on Android physical devices.
4. **Build Size Inspector (`build_size.py`)**:
   - In-memory zip central directory parser comparing new builds against previous runs.
   - Warns on unexpected size regressions and flags uncompressed raw assets (`ZIP_STORED` ≥ 500 KB) packaged into production archives.

---

## ⚡ Server Lifecycle Management

`server_manager.py` manages local server execution without requiring an open terminal window:

1. **In-Place Hot Restart**:
   - Re-executes the server process using `os.execv(sys.executable, [sys.executable] + sys.argv)` to reload backend code in-place while keeping open browser sessions and working directory intact.
2. **Process Controls**:
   - `/api/deployment/server/status`, `/start`, `/stop`, `/restart`, `/end` endpoints manage the daemon process cleanly via PID file tracking.
3. **Desktop & Systemd Integration**:
   - **Linux Desktop Launcher**: Generates `~/.local/share/applications/dev-deployment.desktop` with one click for system app menu launching.
   - **Systemd User Service**: Generates and enables `~/.config/systemd/user/dev-deployment.service` for seamless auto-start on user login.

---

## 📐 Design Rules

1. **Generic, never project-specific.** No hardcoded `apps/<name>`, package names or file names. Use the resolvers (`_resolve_app_dir` / `resolveAppDir`, `resolveAndroidPackageName`, `resolvePlayServiceAccount`).
2. **Per-request project.** Use `get_workspace_root()`; start background threads with `jobs._start_in_context`.
3. **No secrets in projects.** Keys only through `credentials.py`; project files contain identifiers and paths.
4. **Only known commands run.** The API selects templates; it never executes command text from a request.
5. **Visible and honest operations.** State-changing steps log what they run and fail the job on errors.
6. **Standard library only** in the backend; no database, no framework.

---

## 🗂️ File Map

Every tracked file and what it owns. Paths are relative to the repository root.

### Root & config

| File | What it owns |
|---|---|
| `README.md` | User guide: setup, projects, detection, Configure, credentials, building, releases |
| `ARCHITECTURE.md` | This document: how it works, design rules, file map |
| `CONTRIBUTING.md` | Development setup, tests, code standards, roadmap |
| `CHANGELOG.md` | Notable changes per release |
| `SECURITY.md` | Security model and how to report vulnerabilities |
| `FAQ.md` | Questions & answers, troubleshooting |
| `CLAUDE.md` | Instructions for AI coding agents working on this repo |
| `docs/API.md` | REST API reference |
| `docs/adr/` | Architecture Decision Records — why key choices were made |
| `docs/proposals/` | Designed features ready to be built (e.g. Pipelines) |
| `LICENSE` | MIT license |
| `start.sh` | Entry point — checks Python ≥ 3.10, loads `.env`, resolves `WORKSPACE_ROOT`, creates the auth token, starts the server |
| `.env.example` | Template for `WORKSPACE_ROOT`, `DEPLOYMENT_PORT`, `DEPLOYMENT_TMP_DIR`, `DEFAULT_TEAM_ID`, `GOOGLE_CHAT_WEBHOOK_URL` |
| `.gitignore` | Excludes `.env`, keys, pid/log files, IDE files, local config |
| `.shellcheckrc`, `ruff.toml` | Lint settings for Bash and Python |
| `config/deployment_templates.json` | **Command registry** — every command card, grouped `ios`, `android`, `combined`, `release`, `utility` |
| `config/workspaces_list.example.json` | Example of the added-projects list |
| `config/active_workspace.example.txt` | Example default-project pointer |
| `config/workspace_config.json` | *Unused* — leftover from the old developer-dashboard |

---

### Backend — Python

`features/deployment/backend/` — standard library only.

| File | What it owns | Main functions |
|---|---|---|
| `server.py` | HTTP server: routing, `X-API-Token` auth, host/origin checks, `X-Workspace` per-request project, static files (injects the token into `index.html`), multipart uploads, startup migration of inline `.p8` keys | `DeploymentHandler`, `main` |
| `router.py` | Facade re-exporting backend modules to `server.py` | — |
| `config.py` | Project discovery and layout classification, app vs package detection, flavors, apps/deploy config files, auto-scan of bundle IDs / package names / Firebase files, added-projects list | `get_apps`, `inspect_workspace_path`, `scan_app_config`, `scan_all_apps_config`, `rescan_workspace`, `allow_workspace`, `get_workspaces_list`, `load_deploy_config`, `save_deploy_config`, `get_workspace_root` (`_discover_apps_in_workspace`, `_detect_app_in_dir`, `_describe_layout`, `_resolve_app_dir`) |
| `commands.py` | Builds command cards from templates; decides script vs direct execution (`ACTION_MAP`); locks uploads without credentials | `get_commands`, `regenerate_commands` |
| `jobs.py` | Runs jobs as subprocesses with the app's credential env, streams output, per-app locks, history, chained auto-release, iOS cert expiry; job threads keep the request's project | `execute_command`, `get_job`, `stop_job`, `get_running_jobs`, `get_deployment_history`, `check_ios_expiry` |
| `credentials.py` | Key scanning by content, import/upload, private per-user store, status, environment for jobs, migration of old inline `.p8` | `scan_credentials`, `import_credential_path`, `import_credential_bytes`, `remove_credential`, `get_credentials_status`, `job_env`, `migrate_inline_p8` |
| `pipelines/` | Visual pipeline model, step execution engine, custom shell steps, continue-on-failure handling, step reordering, persistent pipeline storage (`storage.py`, `engine.py`) | `load_pipelines`, `save_pipeline`, `delete_pipeline`, `execute_pipeline`, `get_pipeline_run`, `stop_pipeline_run` |
| `notifications/` | Universal webhook dispatch (Slack, Discord, Teams, Google Chat, WhatsApp Meta Cloud/Twilio, Custom Templates), payload templating, incoming CI/CD ingestion gateway with HMAC SHA-256 / token validation (`templates.py`, `channels.py`, `incoming.py`) | `send_deployment_notification`, `test_notification_channel`, `handle_incoming_webhook`, `render_template` |
| `server_manager/` | Server process lifecycle management, desktop launcher generation (`.desktop`), and systemd user service registration (`paths.py`, `desktop.py`, `service.py`) | `get_server_status`, `install_desktop_launcher`, `install_systemd_service`, `get_service_status` |
| `docs_provider.py` | In-app documentation repository provider, dynamic Markdown overview generator, and document security validator | `list_available_docs`, `get_doc_content` |
| `artifacts/` | Local APK/AAB/IPA build artifact scanning, safe path resolution, file metadata extraction, and local download endpoint serving (`network.py`, `scanner.py`, `distributor.py`) | `find_apk_artifact`, `resolve_safe_apk_path`, `get_apk_download_info`, `get_lan_ip` |
| `qr/` | Pure Python QR code generation (zero external pip dependencies), GF(256) Reed-Solomon engine, SVG/ASCII renderers (`matrix.py`, `renderer.py`) | `generate_qr_matrix`, `generate_qr`, `qr_svg`, `qr_ascii` |
| `sentinel/` | Expiry sentinel monitors for Apple certificates (.cer/.p12/.mobileprovision), Android Keystores, and Firebase project configuration mismatch checks (`parsers.py`, `apple_sentinel.py`, `android_sentinel.py`, `firebase_sentinel.py`, `runner.py`) | `check_app_sentinel`, `check_workspace_sentinel`, `check_apple_expiry`, `check_android_keystore_expiry`, `check_firebase_mismatch` |
| `build_size/` | Build size archive diffing, historical artifact tracking, uncompressed raw asset detection (`ZIP_STORED` ≥ 500 KB), breakdown by file type (`formatter.py`, `archive_inspector.py`, `history_tracker.py`, `analyzer.py`) | `find_build_artifact`, `inspect_archive_contents`, `compare_build_size`, `inspect_and_diff_job`, `get_build_size_info` |
| `doctor/` | Pre-flight App Doctor diagnostic suite checking Flutter, Java, Xcode, CocoaPods, Fastlane, Melos, Git, environment sanity (`tool_checks.py`, `project_checks.py`, `runner.py`) | `diagnose_app` |
| `picker.py` | Native folder/file dialogs (`osascript` on macOS, `zenity` on Linux); remembers chosen folders for inspection | `pick_path`, `was_picked` |
| `p8.py` | `.p8` upload endpoint, delegating to `credentials.py` | `upload_p8_key` |

---

### Frontend — Dashboard

`features/deployment/frontend/`

| File | What it owns |
|---|---|
| `index.html` | Page layout: header, Projects bar, app grid + packages list, environment tabs, command cards, *Ready to execute*, Live Terminal / History; **Import Project** dialog; **Configure** dialog with tabs (General, Keys, iOS, Android, Firebase, Release) |
| `app.js` | Fetch wrapper (adds `X-API-Token` and the tab's `X-Workspace`), project tabs (`selectProject`), apps/commands loading and grouping, job run/poll/stop, history, Import Project dialog (`inspectImportFolder`) |
| `setup.js` | Configure dialog: app sidebar, tabs (`showSetupTab`), form load/save, auto-scan, `.p8` dropzone, credential status (`loadCredentialStatus`), Play key upload, folder scan and import (`runCredentialScan`, `importScanned`), native picker helper (`pickNativePath`) |
| `styles.css` | Dashboard styles on top of the UI kit: Import result, Configure tabs and status dots, sidebar button reset |
| `modules/api.js`, `modules/certs.js`, `modules/utils.js` | *Unused* — ES modules not loaded by `index.html` |

---

### Shared UI Assets

`frontend/` — the `developer-dashboard-ui` kit. The page loads the kit from `cdn.jsdelivr.net/gh/sunilbvb/developer-dashboard-ui@main/dist/ui.css` and falls back to the local copy.

| File | What it owns |
|---|---|
| `frontend/css/developer-dashboard-ui-kit.css` | Local fallback of the kit (includes the `button.ui-sidebar-item` reset) |
| `frontend/css/ui-kit.css`, `frontend/css/core.css` | Kit components, base reset and theme variables |
| `frontend/js/ui-kit.js`, `frontend/js/core_utils.js` | Kit interactions and shared helpers (`apiUrl`, toasts) |
| `frontend/dashboard.html` | Shared dashboard shell from the original kit |
| `frontend/developer-dashboard-ui/` | Kit source: components, widget READMEs, showcase, `bundle.py` / `server.py` for building and previewing the kit |

---

### Scripts — Core & Entry

`features/deployment/scripts/`

| File | What it owns |
|---|---|
| `run_build.sh` | Main CLI entrypoint `run_build.sh <action> <app> <env>`: resolves project root, sources `core/json_utils.sh`, executes action |
| `core/json_utils.sh` | Modular coordinator hub sourcing domain core scripts and platform utilities |
| `core/melos_runner.sh` | Melos script detection, naming, argument resolution, and fallback direct execution (`runMelosOrDirect`) |
| `core/fastlane_utils.sh` | Deployment Fastlane folder and Fastfile locators (`resolveDeploymentFastlaneDir`) |
| `core/project_resolver.sh` | App folder, package name, service account, and JSON configuration extractors (`resolveAppDir`, `resolvePlayServiceAccount`, `resolveAndroidPackageName`, `getValueByKey`, `exportAppContents`) |
| `core/retry_utils.sh` | Resilient store upload retry engine with exponential backoff and duplicate-version short-circuiting (`_retryUpload`) |
| `core/release_commands.sh` | Release tool CLI wrappers (`releasePreview`, `releaseChangelog`, `releaseCommit`, `releaseTag`, `releasePush`, `releaseBumpPatch`, `releaseUndo`) |
| `core/multiplatform.sh` | Combined Android + iOS build and deploy orchestrator sharing a single version bump (`deployBothPlatforms`) |
| `core/build_profiles.json` | Named build profiles & environment configurations |
| `json_utils.sh` | Backward-compatibility delegator sourcing `core/json_utils.sh` |

---

### Scripts — Android

| File | What it owns |
|---|---|
| `android/android_utils.sh` | Coordinator hub: sources `android_diagnostics.sh`, `android_build.sh`, `android_upload.sh`; holds `flutterAndroidFlavor`, `findAabFile`, `buildAndUploadAndroid`, `deployAAB` |
| `android/android_build.sh` | Pure build automation: `buildAAB`, `buildAABRaw`, clean build wipe, JDK resolution, Dart defines generation |
| `android/android_upload.sh` | Google Play Store uploads: `runWithAndroidEnv`, `uploadAndroid`, `uploadAAB`, retry wrapper integration |
| `android/android_diagnostics.sh` | Error messages (missing AAB, missing service account with all lookup locations, upload failures) |

---

### Scripts — iOS

| File | What it owns |
|---|---|
| `ios/ios_utils.sh` | `buildIPA`, `deployIPA`, `uploadIPA`, `buildAndUploadIOS`, `findIpaFile`; Apple key resolution (console env vars first) |
| `ios/ios_build.sh` | `buildIPARaw`: CocoaPods, Xcode archive/export, export options, optional device install |
| `ios/ios_upload.sh` | `uploadIPARaw`: TestFlight upload via fastlane or `altool` |
| `ios/ios_diagnostics.sh` | iOS error messages and environment checks |

---

### Scripts — Release

| File | What it owns |
|---|---|
| `release/release_changelog_tagger.dart` | Release CLI entrypoint & coordinator: imports and exports all `src/` modules; handles main execution flow |
| `release/src/models.dart` | Data models and CLI parsing: `GitCommit`, `PackageInfo`, `ReleaseOptions`, `ReleaseMode`, `parseArgs`, `printHelp` |
| `release/src/git_ops.dart` | Git execution engine, commit history reader, tag finders, push runner, and release undo rollback |
| `release/src/workspace_scanner.dart` | Monorepo package scanning, file ownership detection, dependency resolution, and unreleased status report |
| `release/src/branch_governance.dart` | Branch allowlist enforcement, ancestry linearity verification, and tag collision safeguards |
| `release/src/changelog_builder.dart` | Markdown changelog compilation, conventional commit categorizer, commit tables, and changelog prepender |
| `release/src/semver_ops.dart` | Semantic version string bumper (patch/minor/major/build) and `pubspec.yaml` updater |
| `release/src/store_notes.dart` | Consumer-friendly App Store / Play Store "What's New" release notes generator |
| `release/src/release_notifier.dart` | Formatted release summary printer and Google Chat / Slack webhook broadcaster |
| `release_changelog_tagger.dart` | Backward-compatibility entrypoint delegating to `release/release_changelog_tagger.dart` |

---

### Scripts — Security & Keychain

| File | What it owns |
|---|---|
| `security/build_secrets.sh` | Loads secrets from macOS Keychain at compile time |
| `security/setup_keychain.sh` | Configures temporary keychain in CI / build environments |
| `build_secrets.sh` | Backward-compatibility delegator sourcing `security/build_secrets.sh` |

---

### Scripts — Chat Notifications

| File | What it owns |
|---|---|
| `chat/chat_notify.sh` | Wraps a command and posts a result card to `GOOGLE_CHAT_WEBHOOK_URL` |
| `chat/chat_helpers.sh` | Env-file lookup, version detection (`APP_DIR` aware), git info |
| `chat/chat_card_header.sh`, `chat/chat_card_sections.sh`, `chat/chat_card_failures.sh` | Card parts |
| `chat/chat_android_utils.sh`, `chat/chat_ios_utils.sh` | Platform-specific card details |
| `chat_notify.sh` | Top-level entry kept for backward compatibility |

---

### Scripts — Git & Tools

| File | What it owns |
|---|---|
| `git/smart_git.sh`, `git/git_merge_branch.sh`, `git/git_rename_branch.sh`, `git/git_workspace_status.sh` | Stand-alone git helpers (not wired to dashboard buttons) |
| `tools/i18n_scan_strings.py` | Scans source for untranslated strings |
| `tools/fix_with_opacity_with_values.sh` | One-off Flutter `withOpacity()` → `withValues()` migration |

---

### Fastlane

`features/deployment/fastlane/`

| File | What it owns |
|---|---|
| `Fastfile` | Lanes `android upload_android` (Play `internal` track, `SERVICE_ACCOUNT_JSON` path or raw JSON) and `ios testflight_build` |
| `Gemfile`, `Gemfile.lock` | Fastlane dependencies |
| `README.md` | Generated by fastlane |

---

### Server Lifecycle

`features/deployment/bin/` — `start-deployment.sh`, `stop-deployment.sh`, `status-deployment.sh`, `restart-deployment.sh` (background server with a pid file).

---

### Tests & CI

| File | What it covers |
|---|---|
| `tests/test_deployment.py` | Discovery and layouts, flavors, commands, credentials (scan/import/env/migration), import layouts, native picker, per-tab job context |
| `tests/test_api.py` | Router exports, health, workspace list |
| `tests/test_security_guards.py` | Host/origin checks, auth, body limits, webhook auth, UI routes |
| `.github/workflows/ci.yml` | CI: tests and lint |

Run: `python3 -m unittest discover -s tests` (Python ≥ 3.10).

---

### Runtime Data (not in git)

| Path | What it stores |
|---|---|
| `config/workspaces_list.json` | Added projects |
| `<project>/.dev-dashboard/apps_config.json` | Detected apps |
| `<project>/.dev-dashboard/deploy_config.json` | Per-app identifiers, paths, auto-release (no secrets) |
| `<project>/.dev-dashboard/pipelines.json` | Saved visual deployment pipelines |
| `<project>/.dev-dashboard/deployment_history.jsonl` | Job history |
| `<project>/.dev-dashboard/build_sizes.json` | Historical build archive sizes for diffing |
| `~/.config/dev-deployment/auth_token.txt` | API token |
| `~/.config/dev-deployment/credentials.json` | Key ↔ app mapping per project |
| `~/.config/dev-deployment/keys/` | Imported Play service-account keys |
| `~/.appstoreconnect/private_keys/` | Imported App Store Connect `.p8` keys |
| `~/.local/share/applications/dev-deployment.desktop` | 1-Click desktop application launcher |
| `~/.config/systemd/user/dev-deployment.service` | Auto-start systemd background user service |
