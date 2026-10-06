# REST API Documentation 🔌

The Dev Deployment Console provides a robust REST API powering both the web UI and external command-line automation scripts. The server listens on `localhost` (default port `18112`).

---

## 📑 Table of Contents

1. [Conventions & Security](#conventions--security)
2. [Workspaces & Projects](#workspaces--projects)
3. [Apps & Configuration](#apps--configuration)
4. [Job Execution & History](#job-execution--history)
5. [Credentials & Keys](#credentials--keys)
6. [Pre-flight Diagnostics (App Doctor)](#pre-flight-diagnostics-app-doctor)
7. [Certificate & Keystore Expiry Sentinel](#certificate--keystore-expiry-sentinel)
8. [Build Size Inspector & Diff](#build-size-inspector--diff)
9. [Local APK Hosting & QR Code](#local-apk-hosting--qr-code)
10. [Saved Pipelines](#saved-pipelines)
11. [Server Management & 1-Click Launchers](#server-management--1-click-launchers)
12. [Team Webhook Notifications](#team-webhook-notifications)
13. [Documentation Provider](#documentation-provider)
14. [iOS OTA Installation & Direct IPA Hosting](#ios-ota-installation--direct-ipa-hosting)
15. [Wireless ADB Device Management & Parallel Push](#wireless-adb-device-management--parallel-push)
16. [Build Time Profiler & Bottleneck Heatmap](#build-time-profiler--bottleneck-heatmap)
17. [Smart Silent Cache Warmer](#smart-silent-cache-warmer)

---

## Conventions & Security

| Header / Query | Required | Meaning |
|:---|:---|:---|
| `X-API-Token` | Required for all `/api/*` | Bearer auth token from `~/.config/dev-deployment/auth_token.txt` |
| `?token=` or `?auth=` | Media / APK streaming | Query parameter fallback for downloading APKs or rendering QR SVGs |
| `X-Workspace` | Optional | Absolute directory of target project workspace (defaults to active root) |
| `Content-Type: application/json` | POST endpoints | Required for all JSON payloads (except multipart `.p8` upload) |

### Security Rules
- **Host Header Validation:** Non-localhost `Host` headers (`127.0.0.1`, `localhost`) are rejected with `403 DNS Rebinding Rejected`.
- **CORS Isolation:** Unapproved external browser origins are rejected with `403 Cross-Origin Request Rejected`.
- **Body Size Limit:** JSON POST bodies exceeding 1 MB are rejected with `413 Payload Too Large`.
- **Response Format:** All endpoints return JSON with `"success": true|false`. On failure, an descriptive `"error"` message is included.

```bash
# Example API call with curl:
TOKEN=$(cat ~/.config/dev-deployment/auth_token.txt)
curl -s -H "X-API-Token: $TOKEN" \
     -H "X-Workspace: /home/sunil-bakale/IdeaProjects/dev-deployment" \
     http://localhost:18112/api/deployment/apps
```

---

## Workspaces & Projects

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/workspaces` | – | Returns list of added projects, default workspace, and directory existence check. |
| `POST` | `/api/deployment/workspace/allow` | `{"path": "/path/to/project"}` | Adds a new project workspace to `config/workspaces_list.json`. |
| `POST` | `/api/deployment/workspace/remove` | `{"path": "/path/to/project"}` | Removes a project tab from the console list (source files remain untouched). Returns `409` if a job is running. |
| `GET` | `/api/deployment/inspect-path` | `?path=/path/to/inspect` | Inspects arbitrary directory: detects layout, app count, package count, Melos monorepo status, and framework stack. |
| `POST` | `/api/deployment/pick` | `{"kind": "folder"\|"file"}` | Opens OS native folder picker dialog on server host and returns selected path. |
| `POST` | `/api/deployment/workspace/select` | `{"path": "/path/to/project"}` | Sets server-wide default workspace. |

---

## Apps & Configuration

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/apps` | – | List of detected apps and non-deployable packages: `id`, `name`, `path`, `stack`, `is_package`, `version`, `icon`. |
| `POST` | `/api/deployment/apps` | `{"id", "name", "path", ...}` | Register or update an application metadata record manually. |
| `POST` | `/api/deployment/rescan-workspace` | – | Forces full re-detection of applications and packages across the project tree. |
| `GET` | `/api/deployment/deploy-config` | – | Full deployment configuration object from `<project>/.dev-dashboard/deploy_config.json`. |
| `POST` | `/api/deployment/deploy-config/save` | Full config payload | Validates schema and saves deployment configuration. |
| `GET` | `/api/deployment/scan-config` | `?app=<app_id>` | Runs static code scanner to detect bundle IDs, package names, flavors, and Firebase files for one app. |
| `POST` | `/api/deployment/scan-all` | `{"force": true}` | Runs static auto-scanner across all apps in the active project. |
| `GET` | `/api/deployment/templates` | – | Retrieves template command definitions grouped by category. |
| `GET` | `/api/deployment/commands` | `?app=<app_id>` | Returns executable command tiles for the specified app and its flavors. |
| `POST` | `/api/deployment/regenerate` | – | Re-runs command discovery and builds executable parameter maps. |

---

## Job Execution & History

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `POST` | `/api/deployment/execute` | `{"app", "templateId", "flavor", "confirmed"}` | Starts asynchronous build job. Rejects arbitrary commands; only pre-verified template actions run. |
| `GET` | `/api/deployment/job` | `?id=<job_id>` | Polls job execution state: `running`, `success`, `error`, `stopped`, stdout/stderr chunks, duration. |
| `POST` | `/api/deployment/stop` | `{"jobId": "<job_id>"}` | Sends `SIGTERM` (followed by `SIGKILL`) to terminate active process group. Releases app busy lock. |
| `GET` | `/api/deployment/running-jobs` | – | Returns list of all currently active jobs across all projects. |
| `GET` | `/api/deployment/history` | `?app=&flavor=&status=&limit=50` | Queries past execution records from `<project>/.dev-dashboard/deployment_history.jsonl`. |

---

## Credentials & Keys

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/credentials` | `?app=<app_id>` | Returns credential resolution status (Play service account, Apple `.p8` key, Issuer UUID). Never returns private secrets. |
| `POST` | `/api/deployment/credentials/scan` | `{"folder": "/scan/path"}` | Deep scans folder for Google Play JSONs, Apple `.p8` keys, and Firebase configs by file content analysis. |
| `POST` | `/api/deployment/credentials/import` | `{"path", "app"?, "flavor"?, "issuerId"?}` | Securely copies credential file to `~/.config/dev-deployment/` with `chmod 600`. |
| `POST` | `/api/deployment/credentials/upload` | `{"filename", "contentBase64", ...}` | Imports uploaded base64 key directly into user keychain directory. |
| `POST` | `/api/deployment/credentials/remove` | `{"kind", "app"?}` | Disassociates key mapping from specified application. |
| `POST` | `/api/deployment/p8/upload` | Multipart or JSON payload | Uploads App Store Connect PKCS#8 private key file. |

---

## Pre-flight Diagnostics (App Doctor)

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/doctor` | `?app=<app_id>&flavor=<flavor>` | Runs 12+ pre-flight diagnostics (Flutter SDK, Android SDK, CocoaPods, keystores, provisioning profiles, Git clean status, Firebase configs). |

### Response Schema:
```json
{
  "success": true,
  "appId": "customer_app",
  "flavor": "prod",
  "overallStatus": "pass", // "pass" | "warn" | "fail"
  "summary": { "passed": 11, "warnings": 1, "failures": 0, "total": 12 },
  "checks": [
    {
      "id": "flutter_sdk",
      "category": "SDK & Tools",
      "name": "Flutter SDK Installation",
      "status": "pass",
      "message": "Flutter 3.24.3 (Dart 3.5.3) found at /opt/flutter/bin/flutter",
      "hint": null
    },
    {
      "id": "android_keystore",
      "category": "Signing & Credentials",
      "name": "Android Release Keystore",
      "status": "warn",
      "message": "Keystore certificate expires in 28 days",
      "hint": "Renew keystore using keytool before publishing to Google Play"
    }
  ]
}
```

---

## Certificate & Keystore Expiry Sentinel

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/sentinel` | `?app=<app_id>&flavor=<flavor>` | Proactively checks Apple `.p8` keys, iOS distribution certs, Android upload keys, and cross-platform Firebase project IDs. |

### Response Schema:
```json
{
  "success": true,
  "appId": "customer_app",
  "flavor": "prod",
  "status": "warning", // "ok" | "warning" | "critical"
  "message": "1 certificate requires attention",
  "alerts": [
    {
      "type": "apple_cert",
      "severity": "warning",
      "name": "Apple Distribution Certificate",
      "expiresOn": "2026-10-25",
      "daysRemaining": 23,
      "message": "Expires in 23 days (renew in Apple Developer portal)"
    }
  ],
  "firebase": {
    "mismatch": false,
    "androidProjectId": "acme-prod",
    "iosProjectId": "acme-prod"
  }
}
```

---

## Build Size Inspector & Diff

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/build-size` | `?jobId=<id>&app=<app>&flavor=<flavor>` | Inspects ZIP central directory of generated AAB/APK without disk extraction. Compares byte size against previous run and flags uncompressed raw assets (`ZIP_STORED` ≥ 500 KB). |

### Response Schema:
```json
{
  "success": true,
  "artifact": "app-prod-release.aab",
  "sizeBytes": 25375539,
  "formattedSize": "24.2 MB",
  "previousSize": 21390950,
  "deltaBytes": 3984589,
  "deltaFormatted": "+3.8 MB",
  "deltaPercent": "+18.6%",
  "severity": "warning", // "ok" | "warning" | "critical"
  "uncompressedOversizedAssets": [
    {
      "path": "base/assets/sample_video.mp4",
      "sizeBytes": 2048576,
      "formattedSize": "1.95 MB",
      "method": "ZIP_STORED"
    }
  ]
}
```

---

## Local APK Hosting & QR Code

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/download/<target>` | `?token=<auth_token>` | Streams generated `.apk` file for direct wireless installation. Verified via query token or `X-API-Token`. |
| `GET` | `/api/deployment/qr` | `?text=<url>&token=<auth_token>` | Generates SVG QR code representation of the download URL for mobile camera scanning. |

---

## Saved Pipelines

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/pipelines` | `?app=<app_id>` | Returns saved multi-step deployment pipelines for the app. |
| `POST` | `/api/deployment/pipelines/save` | `{"app", "pipeline": {"id", "name", "steps": [...]}}` | Saves or updates a visual pipeline definition. |
| `POST` | `/api/deployment/pipelines/delete` | `{"app", "pipelineId": "<id>"}` | Deletes a saved pipeline definition. |
| `POST` | `/api/deployment/pipelines/run` | `{"app", "pipelineId", "flavor", "confirmed"}` | Triggers sequential step-by-step pipeline execution with stop-on-failure safety. |
| `GET` | `/api/deployment/pipelines/run` | `?id=<run_id>` | Returns live execution progress, active step index, and per-step logs. |
| `POST` | `/api/deployment/pipelines/stop` | `{"runId": "<run_id>"}` | Aborts active pipeline execution and releases the app lock. |

---

## Server Management & Lifecycle Controls

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/server-status` | – | Lightweight heartbeat ping returning online status, port, and auth token for local/file:// clients. |
| `GET` | `/api/deployment/server/status` | – | Detailed server telemetry: uptime seconds, PID, memory, active workspace root. |
| `GET` | `/api/deployment/server/service-status` | – | Detects if desktop shortcut or systemd user service is installed on host. |
| `POST` | `/api/deployment/server/start` | `{"port": 18112}` | Spawns background server process. |
| `POST` | `/api/deployment/server/stop` | – | Gracefully shuts down active server process. |
| `POST` | `/api/deployment/server/end` | – | Graceful termination alias for Stop Server. |
| `POST` | `/api/deployment/server/restart` | – | Triggers automated in-place process restart via `os.execv`. |
| `POST` | `/api/deployment/server/install-desktop` | – | Creates native `.desktop` application shortcut in `~/.local/share/applications/`. |
| `POST` | `/api/deployment/server/install-service` | – | Installs and activates systemd user login service `dev-deployment.service`. |

---

## Universal Webhooks & CI/CD Ingestion

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `POST` | `/api/deployment/notifications/test` | `{"url", "provider", "app"?, "custom_template"?, "custom_headers"?, "phone"?}` | Sends immediate test card to any webhook (Slack, Discord, Teams, Google Chat, WhatsApp, Custom template, or Generic JSON). |
| `POST` | `/api/deployment/webhook/incoming` | JSON or form-urlencoded | Universal incoming webhook ingestion. Triggers commands or automated pipelines from GitHub, GitLab, Slack, or cURL. |
| `POST` | `/api/deployment/webhook/incoming/<provider>` | `github` \| `gitlab` \| `slack` \| `generic` | Provider-specific routing alias with tailored header and payload parsers. |
| `POST` | `/api/deployment/webhook` | `{"app", "templateId", "flavor"}` | Legacy endpoint maintained for backward compatibility. |

### Incoming Webhook Authentication
Incoming requests are accepted if ANY of the following match:
1. `X-Webhook-Secret: <secret>` or `X-Gitlab-Token: <secret>` equals `WEBHOOK_SECRET`.
2. `Authorization: Bearer <secret>` equals `WEBHOOK_SECRET`.
3. `?secret=<secret>` or `?token=<secret>` query parameter equals `WEBHOOK_SECRET`.
4. `X-Hub-Signature-256: sha256=<hmac>` validates against `WEBHOOK_SECRET` (GitHub standard).
5. `X-Slack-Signature: v0=<hmac>` with `X-Slack-Request-Timestamp` validates against `WEBHOOK_SECRET` (Slack standard).
6. Authorized session header `X-API-Token: <token>`.

### Ingestion Triggers:
- **Trigger Pipeline:** `{"app": "my_app", "pipeline": "full_release", "flavor": "prod"}`
- **Trigger Command:** `{"app": "my_app", "templateId": "build_aab", "flavor": "prod"}`
- **Slack Slash Command:** `/deploy my_app prod build_aab` or `/deploy pipeline full_release my_app`
- **GitHub Ping:** `{"zen": "..."}` with `X-GitHub-Event: ping` returns `200 Pong`.

---

## Documentation Provider

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/docs/list` | – | Returns list of all available documentation guides and categories. |
| `GET` | `/api/deployment/docs` | `?doc=<id>` | Returns markdown document content for display in the interactive docs viewer. |

---

## iOS OTA Installation & Direct IPA Hosting

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/ipa-info` | `?app=<app_id>&flavor=<flavor>` | Locates latest `.ipa` artifact and returns direct download URL and native `itms-services://` OTA link. |
| `GET` | `/api/deployment/download-ipa/<target>` | `?token=<auth_token>` | Streams compiled `.ipa` binary with chunked range support. |
| `GET` | `/api/deployment/ota/manifest.plist` | `?app=<app>&flavor=<flavor>&token=<token>` | Generates Apple's dynamic XML `manifest.plist` for 10-second Camera QR OTA install. |

---

## Wireless ADB Device Management & Parallel Push

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/adb/devices` | – | Discovers connected USB, Wi-Fi, and emulator Android devices via `adb devices -l`. |
| `POST` | `/api/deployment/adb/connect` | `{"ip": "192.168.1.50", "port": 5555}` | Pairs wireless device via `adb connect`. |
| `POST` | `/api/deployment/adb/disconnect` | `{"ip": "192.168.1.50", "port": 5555}` | Disconnects device via `adb disconnect`. |
| `POST` | `/api/deployment/adb/push` | `{"app": "...", "deviceIds": ["..."]}` | Pushes and installs APK in parallel across all selected devices. |

---

## Build Time Profiler & Bottleneck Heatmap

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/build-profile` | – | Analyzes latest completed job log into 6 mobile phases with bottleneck detection (≥30%). |
| `GET` | `/api/deployment/job/profile` | `?job_id=<id>` | Analyzes compilation timings and phase breakdown for specific historical job. |

---

## Smart Silent Cache Warmer

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/cache-warmer/status` | – | Returns daemon status (`idle`, `warming`, `ready`), watched branch, and last warm time. |
| `POST` | `/api/deployment/cache-warmer/warm` | – | Triggers background dependency resolution (`flutter pub get`) when no jobs are active. |

---

## Pre-Release Deep Link & Universal Link Validator

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/deep-links` | `?app=<app_id>&domain=<override>` | Scans manifests/entitlements and tests live `assetlinks.json` and `apple-app-site-association` endpoints. |
| `POST` | `/api/deployment/deep-links/verify` | `{"domain": "...", "packageName": "...", "fingerprint": "...", "teamId": "...", "bundleId": "..."}` | Verifies target domain web fingerprints against expected production mobile credentials. |

---

## Store Metadata & Localized Release Notes

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/metadata` | `?app=<app_id>` | Reads multi-locale Fastlane metadata and release notes with character counts and store policy limits. |
| `POST` | `/api/deployment/metadata/save` | `{"app": "...", "platform": "android|ios", "locale": "...", "releaseNotes": "...", "title": "..."}` | Atomically saves localized release notes and metadata back to project Fastlane structure. |
| `GET` | `/api/deployment/metadata/preview` | `?app=<app>&platform=<android|ios>&locale=<loc>` | Returns mockup preview data for mobile store update card. |

---

## Zero-Friction Crash Symbol Vault

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/symbols` | `?app=<app_id>&flavor=<flavor>` | Discovers ProGuard/R8 `mapping.txt` and Apple `.dSYM` archives with file sizes, line counts, and SHA-256 digests. |
| `GET` | `/api/deployment/symbols/download` | `?app=<app_id>&flavor=<flavor>&token=<token>` | Downloads compiled crash symbols as an assembled `.zip` archive for Firebase Crashlytics or Sentry. |

---

## Semantic Version Bumper & Git Conventional Changelog

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/version` | `?app=<app_id>` | Returns current `pubspec.yaml` semantic version and previews next patch, minor, major, and build bumps. |
| `POST` | `/api/deployment/version/bump` | `{"app": "...", "bumpType": "patch|minor|major|build|custom", "customVersion": "...", "customBuild": 12}` | Safely updates `pubspec.yaml` version while preserving all YAML comments and structure. |
| `GET` | `/api/deployment/version/changelog` | `?app=<app_id>&since=<tag>&max=50` | Formats git commits into Conventional Commit Markdown changelog and concise Play Store bullet notes (&le; 500 chars). |

---

## APK / IPA Security & Dangerous Permissions Inspector

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| `GET` | `/api/deployment/security/permissions` | `?app=<app_id>` | Audits Android permissions, cleartext HTTP, exported components, and Apple privacy manifest strings. |

