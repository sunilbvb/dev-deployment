# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); commits follow [Conventional Commits](https://www.conventionalcommits.org).

## [Unreleased]

### Added

- **Universal Webhooks & Multi-Destination Alerts**: Multi-channel deployment notifications for Google Chat, Slack, Discord, Microsoft Teams, and WhatsApp (Meta Cloud API + Twilio REST API) with instant test dispatch.
- **Custom Payload & Header Engine**: Configurable JSON payload templates with dynamic variable interpolation (`{app}`, `{status}`, `{flavor}`, `{version}`, `{commit}`, `{author}`, `{summary}`, `{run_id}`, `{download_url}`) and custom HTTP headers.
- **Universal Incoming CI/CD Ingestion Gateway**: Ingest external triggers from GitHub Actions, GitLab CI/CD, Slack slash commands, and generic cURL triggers with HMAC SHA-256 (`X-Hub-Signature-256`), GitLab token (`X-Gitlab-Token`), Slack signature, and Bearer token verification.
- **Visual Pipeline Builder UI**: Interactive pipeline creator with categorized step picker (Diagnostics, Builds, Uploads, Quality/Test, Custom Shell), custom shell command steps, step reordering, continue-on-failure toggles, and live terminal progress tracking.
- **Server Lifecycle Management**: In-place server hot restart (`os.execv`), background daemon process controls (`/api/deployment/server/status`, `/start`, `/stop`, `/restart`, `/end`), 1-click Linux `.desktop` launcher creation, and auto-start systemd user service registration.
- **Local Artifact Hosting & Wireless QR Scanning**: Automatic local HTTP hosting of built APKs and pure Python QR code generation (SVG/PNG matrix, zero pip dependencies) for cable-free LAN installation on mobile devices.
- **Pre-flight App Doctor & Expiry Sentinels**: 1-click system diagnostics (Flutter, Java, CocoaPods, Xcode, Fastlane, Melos, Git), proactive expiration monitors for Apple certificates, `.p8` keys, and Android keystores (< 30 days), and cross-platform Firebase project ID mismatch detection.
- **Build Size Inspector & Archive Diffing**: Archive size regression comparison against historical builds and deep zip inspection alerting on uncompressed raw assets (`ZIP_STORED` ≥ 500 KB).
- **Generic project detection** for every layout: single app (with or without local packages), several apps, apps with shared packages, Melos monorepos and Dart pub workspaces — any folder names, nested packages, Flutter plugins recognised as packages, `main_*.dart` flavor entry points recognised as apps.
- **Import Project** with the native folder dialog (macOS `osascript`, Linux `zenity`), showing the detected layout, apps and packages before adding.
- **Remove a project** (× on its tab): drops it from the list without touching the folder or its settings.
- **Project tabs**: each added project is a tab; the project is chosen per browser tab (`X-Workspace`), so several projects can be open at once.
- **Credentials handled by the tool**: scan any folder for Play service accounts, App Store Connect `.p8` keys and Firebase configs by content; import with one click; keys stored outside the project (`chmod 600`); credentials passed to every job as environment variables; status shown per app.
- **Configure dialog tabs** (General, Keys, iOS, Android, Firebase, Release) with credential status dots.
- **Release logging**: commit table with included/skipped reasons, every mutating git command with its output, final release summary.
- Full Release pushes a release that was already tagged locally (e.g. after Bump Patch).
- Melos workspaces without deploy scripts run the build/upload steps directly.
- Packages listed separately as *not deployable*; commands grouped by platform.
- Documentation: `ARCHITECTURE.md`, `docs/API.md`, `docs/adr/`, `docs/proposals/0001-pipelines.md`, `SECURITY.md`, `CLAUDE.md`, this changelog.

### Changed

- **Modular Backend Feature Architecture**: Refactored monolithic backend files into dedicated, single-responsibility feature packages:
  - `notifications/`: `templates.py`, `channels.py`, `incoming.py`
  - `pipelines/`: `storage.py`, `engine.py`
  - `doctor/`: `tool_checks.py`, `project_checks.py`, `runner.py`
  - `sentinel/`: `parsers.py`, `apple_sentinel.py`, `android_sentinel.py`, `firebase_sentinel.py`, `runner.py`
  - `build_size/`: `formatter.py`, `archive_inspector.py`, `history_tracker.py`, `analyzer.py`
  - `qr/`: `matrix.py`, `renderer.py`
  - `artifacts/`: `network.py`, `scanner.py`, `distributor.py`
  - `server_manager/`: `paths.py`, `desktop.py`, `service.py`
- **Modular Scripts Directory Architecture**: Reorganized deployment shell scripts and release tools into specialized domain folders: `core/` (common resolution & build profiles), `release/` (Dart tagger & changelog generator), `security/` (Keychain & secrets injection), `git/` (branch & merge utilities), and `tools/` (maintenance & string scanning), while preserving root backward-compatibility delegator entrypoints.
- **Modularized Core Scripts**: Refactored the monolithic 997-line `core/json_utils.sh` into single-responsibility shell modules: `melos_runner.sh`, `fastlane_utils.sh`, `project_resolver.sh`, `retry_utils.sh`, `release_commands.sh`, and `multiplatform.sh`, keeping `json_utils.sh` as a lightweight coordinator hub.
- App IDs are folder names; display names still come from `pubspec.yaml`.
- `.p8` keys are no longer embedded in `deploy_config.json`; existing inline keys are migrated out on startup.
- Android package names, app folders and the Play key are resolved for any layout instead of `apps/<app>` and fixed file names.
- Credentials imported in the console take precedence over `env/<flavor>.json` in iOS scripts.
- The release tool works without a root `pubspec.yaml` and attributes commits by exact package paths.
- `FILES.md` became `ARCHITECTURE.md`; the API reference moved to `docs/API.md`.

### Removed

- **Deploy All Apps** (batch deploy) and the `batch-plan` API.
- Recent-workspaces dropdown, manual path field and global workspace switching in the UI.
- The non-functional **Inject Melos Scripts** button.

### Fixed

- API calls from the page did not send the auth token, so no apps or commands loaded.
- Running a command crashed the server (`KeyError: 'command'`), and requests with a selected workspace crashed it (`router.config`).
- **Stop** did not stop jobs (wrong route and field); **Regenerate Commands** called a missing route and had a wrong signature.
- "Auto-run Release after successful Deploy/Upload" never ran (read an unsaved setting and a non-existent action).
- Android uploads failed with "package_name must be provided" for any project without bundled profiles.
- Release commands pointed to a non-existent script path in non-Melos workspaces; seven release actions and four utility actions called non-existent script functions.
- A Gyo release included Gyo Business commits (path prefix matching); unrelated packages appeared as "tooling" in every changelog.
- Section headings were stripped from tag and commit messages.
- A failed git push was reported as success.
- Discovery treated `ios/` folders as native apps when using `apps/**` globs, dropped the root app when local packages existed, and hung on large `pubspec.yaml` files.
- Flavor tabs showed for apps without flavors; all commands were grouped under "Release".
- Setup sidebar buttons showed browser default styling.
- Tests wrote a dummy `.p8` into the real `~/.appstoreconnect` folder.

## Earlier history

Before this changelog, changes were recorded only in git history (`git log`), including: security hardening (DNS-rebinding protection, API auth on all endpoints, command quoting, request size limits), workspace discovery and flavor detection improvements, production confirmation gate, deployment history, system health checks and notifications.
