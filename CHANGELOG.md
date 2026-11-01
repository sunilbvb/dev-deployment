# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); commits follow [Conventional Commits](https://www.conventionalcommits.org).

## [Unreleased]

### Added
- MCP server (`features/mcp/`, Dart, built on `dart_mcp`, stdio): lets AI clients list apps, run builds, poll jobs and read history. See `docs/proposals/0004-mcp-server.md`.
- Run timer: the Live Terminal timer now ends with a `⏱ Total time: 12m 34s` line and keeps the final duration on screen when a job finishes, fails or is stopped.
- Keep awake: on macOS every job runs under `caffeinate -i -w <pid>`, so the Mac no longer idle-sleeps mid-build or mid-upload; released when the job ends ([proposal 0002](docs/proposals/0002-after-build-power-action.md) task 1.2).
- Docs: [proposal 0003](docs/proposals/0003-release-notes.md) records what is built for release notes, the store limits, and the pending list; README, FAQ, ARCHITECTURE, FEATURES and API updated.
- Languages per app (`release_locales`), editable in the Run panel and readable from the store listing (`fastlane android|ios list_locales`).
- History: a "Release notes" button opens a finished build's notes (add / edit / save; iOS can also publish them to the TestFlight build). Android is save-only because Play cannot edit a published release.
- `/execute` accepts `releaseNotes` (`{locale: text}`); history entries record `platform`, `buildNumber`, `version` and `releaseNotes`.
- Per-version release notes: `changelogs/<build>.txt` (Android) and `release_notes_<build>.txt` (iOS) win over the shared default; the Store Metadata editor has a Version / build field. `save` accepts `version`.
- `POST /api/deployment/metadata/update-build` and the `ios update_testflight_notes` lane update the TestFlight notes of an already-uploaded build (editor button "Push notes to TestFlight build").
- Release notes are optional and multi-language. They ship with every Play / TestFlight upload when present (`release_notes` per language / `localized_build_info`) and never block an upload. Sources, in order: the Run panel (inline, no confirmation; autofilled from the build's, default or last build's notes), `RELEASE_NOTES_JSON` / `RELEASE_NOTES`, then fastlane metadata files.
- iOS OTA install: the QR now encodes an HTTPS install page (`/api/deployment/ota/install`) with an Install button, because iOS Camera ignores bare `itms-services://` codes.
- HTTPS support: `--tls-cert` / `--tls-key` (or `DEPLOYMENT_TLS_CERT` / `DEPLOYMENT_TLS_KEY`) serve over TLS (use `mkcert` and trust its root CA on the iPhone). `--public-url` / `DEPLOYMENT_PUBLIC_URL` points OTA links at an https tunnel (Cloudflare Tunnel, ngrok).
- `ipa-info` returns `installPageUrl`, `otaReady` and `otaWarning`; plain-HTTP servers now warn that iOS OTA cannot work.

### Fixed

- iOS build: when `flutter build ipa` exits 0 but leaves no IPA (archive only), the archive is now exported with `xcodebuild -exportArchive`; if that fails the build fails with the reason instead of a later "IPA file not found".
- iOS raw upload: the "IPA file not found" message was swallowed by command substitution, so the job failed with no reason. It now goes to stderr and shows in the log.
- Play upload failed with `<locale> - Invalid request` when the release notes had a language the Play listing lacks (e.g. `de`): notes are now sent only for languages the listing has (`de` maps to `de-DE`); others are skipped with a warning.
- Android upload aborted silently before reaching Play: the new AAB pre-flight checks returned `grep`'s exit 1 under `set -euo pipefail` when the AAB had no foreground-service permissions. The Play lane also passed the non-existent `release_notes` option; notes now go through `metadata_path` changelogs.
- Store uploads fail fast, with a fix hint, on errors a retry can never fix: Play Console declaration errors (e.g. "Foreground Service permissions") and App Store Connect 90062 ("must contain a higher version than the previously approved version"). Transient errors still retry 3x.
- Known store errors now live in `features/deployment/scripts/core/known_store_errors.tsv` (class, pattern, hint); add a line to teach the tool a new error. Override the file with `KNOWN_STORE_ERRORS_FILE`.
- `run_build.sh` forces a UTF-8 locale when the environment has none (CocoaPods crashed with `Unicode Normalization not appropriate for ASCII-8BIT`).
- Android upload preflight: warns before uploading when the AAB declares foreground-service permissions (needs `bundletool`; never blocks).
- `_retryUpload` watchdog left a `sleep` running that kept the job's output pipe open for up to 300s after an attempt finished; it is now killed with the watchdog.
- `deployBothPlatforms` still runs iOS when Android fails, then reports both exit codes and returns failure if either failed.
- `uploadAndroid <APP>_<ENV>` for a profile not in `build_profiles.json` (e.g. `GYO_BUSINESS_QA`) resolved the default (prod) package, so QA/dev AABs failed with "APK has the wrong package name". The flavor is now taken from the profile's env.
- Android uploads now verify the AAB's real package (via `bundletool`, when installed) against the upload package before calling Play, and "APK has the wrong package name" fails fast with a fix hint instead of retrying 3x.
- `find_apk_artifact` treated an unknown app id as the workspace root when the workspace path was a symlink (macOS `/var` -> `/private/var`), returning another app's APK; paths are now compared resolved.

- **Profile names not in `build_profiles.json`**: `buildAndUploadIOS GYO_DEV`-style calls (from Melos wrapper scripts) failed with "app_name and secret_file must be provided". `getProfileValue` now derives app, env and secret file from `<APP>_<ENV>` when the app exists in the workspace. When a profile still cannot be resolved, the job log now says why and how to fix it instead of only "must be provided".

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
- **Modularized Android Automation Scripts**: Decomposed the monolithic 760-line `features/deployment/scripts/android/android_utils.sh` into single-responsibility modules matching the iOS pattern: `android_build.sh` (pure build automation & Flutter compilation), `android_upload.sh` (Play Store Fastlane upload & env wrapper), and `android_utils.sh` (lightweight coordinator hub sourcing sub-components).
- **Modularized Dart Release Automation Suite**: Decomposed the monolithic 2,074-line `features/deployment/scripts/release/release_changelog_tagger.dart` into clean domain-specific modules under `release/src/`: `models.dart` (models & CLI options), `semver_ops.dart` (version bumping), `store_notes.dart` (app store notes), `git_ops.dart` (git execution & tag operations), `branch_governance.dart` (branch allowlist & ancestry verification), `workspace_scanner.dart` (monorepo & dependency scanning), `changelog_builder.dart` (markdown generation & commit tables), and `release_notifier.dart` (summary printing & webhook dispatch), preserving 100% backward compatibility for all callers.
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
