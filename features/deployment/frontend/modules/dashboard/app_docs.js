/**
 * app_docs.js — Documentation & Knowledge Hub Module
 * Renders embedded and server-fetched markdown documentation with code syntax,
 * handles docs modal lifecycle, navigation, and sidebar doc selection.
 */

const DEFAULT_EMBEDDED_DOCS = {
    overview: {
        title: "Console Overview & Quickstart",
        category: "Getting Started",
        filename: "Overview",
        content: `# 🚀 Dev Deployment Console — Overview & Guide

Welcome to the **Dev Deployment Console** — a lightweight, zero-dependency developer dashboard and automation tool for Flutter and mobile application deployments across multiple environments (Dev, QA, Production).

---

## ⚡ Core Capabilities & Features

1. **Multi-App Flutter Deployments & Flavor Support**
   - Automatically detects single apps, Melos monorepos, and multi-app workspaces.
   - Generates and executes parameterized Fastlane & Flutter deployment commands.
   - Clean separation of Dev, QA, and Production environments with production deploy confirmation guards.

2. **Saved Pipelines (Chained Workflows)**
   - Create and save multi-step deployment sequences (e.g. \`Pre-flight Diagnostics\` → \`Build AAB\` → \`Upload to Play Store\`).
   - Stop-on-failure safety and live step-by-step progress tracking.

3. **Pre-flight "App Doctor" (1-Click Diagnostics)**
   - 1-click comprehensive system and project health evaluation before running long builds.
   - Inspects Flutter SDK, Android SDK, CocoaPods, keystores, \`.p8\` Apple keys, provisioning profiles, Git clean status, and Firebase configurations.

4. **Local APK Hosting & QR Code Scan-to-Install**
   - Instantly hosts completed Android \`.apk\` builds over local HTTP (\`/api/deployment/download/<job_id>\`).
   - Generates a terminal & UI QR code for instant phone camera scan-and-install over Wi-Fi without cables or Firebase App Distribution setup.

5. **Outgoing Webhooks (Slack / Discord / Microsoft Teams)**
   - Automated deployment notifications to team channels on build completion or failure.
   - Rich card layouts with status badges, elapsed duration, commit logs, and direct APK download links.

6. **Certificate & Keystore Expiry Sentinel**
   - Proactive warnings on dashboard:
     - Apple \`.p8\` API keys and distribution certificates expiring within 30 days.
     - Android upload keys nearing validity limits.
     - Cross-platform Firebase project ID mismatches (e.g. dev config in a production build).

7. **Build Size Inspector & Diff**
   - Fast archive size comparison against previous successful runs (\`AAB: 24.2 MB (+3.8 MB, +18%) ⚠️\`).
   - Deep zip central directory inspection without extracting files to disk.
   - Alerts developers if huge uncompressed raw assets (\`ZIP_STORED\` ≥ 500 KB) are accidentally packaged into production bundles.

---

## 🏁 Starting the Deployment Server

To connect this web console to your real local projects, start the backend server from your terminal:

\`\`\`bash
# 1. From repository root:
./start.sh

# Or directly with Python:
python3 features/deployment/backend/server.py --port 18112
\`\`\`

- **Default Port:** \`http://localhost:18112\`
- **Security:** Protected by local bearer auth token (\`~/.config/dev-deployment/auth_token.txt\`).
- **Zero Third-Party Dependencies:** Written in 100% Python standard library.
`
    },
    examples: {
        title: "End-to-End Workflow Examples & Guides",
        category: "Getting Started",
        filename: "docs/EXAMPLES.md",
        content: `# End-to-End Workflow Examples & Architecture Flows 🚀

This guide provides practical, step-by-step walkthroughs of common mobile deployment scenarios, illustrating the complete data flow from the UI, through the Python REST API, to execution and distribution.

---

## 📑 Workflow Index
1. **Flow 1: First-Time Project Import & Auto-Scan**
2. **Flow 2: Multi-Environment Build (Dev / QA / Prod)**
3. **Flow 3: Wireless Testing (Camera QR & Multi-Device ADB Push)**
4. **Flow 4: Chained Release Pipeline (Doctor → Build → Inspect → Fastlane → Webhook)**
5. **Flow 5: Inbound CI/CD & Two-Way ChatOps (Slack / GitHub)**
6. **Flow 6: Pre-Release Sentinel & Build Size Diffing**

---

## Flow 1: First-Time Project Import & Auto-Scan
1. **Directory Inspection**: Call \`GET /api/deployment/inspect-path?path=/path/to/project\` to detect project type (Flutter single-app or Melos monorepo).
2. **Workspace Registration**: Call \`POST /api/deployment/workspace/allow\` with \`{"path": "/path/to/project"}\`.
3. **1-Click Auto-Scan**: Call \`POST /api/deployment/scan-all\`. Parses \`build.gradle\`, \`.xcconfig\`, Google Services JSONs, and Apple \`.p8\` keys to auto-populate flavors, package IDs, and keystores.
4. **Dynamic Commands**: Command generator creates executable tiles separated cleanly into **Dev**, **QA**, and **Prod** tabs.

---

## Flow 2: Multi-Environment Build (Dev / QA / Prod)
1. **Inspect Commands**: Call \`GET /api/deployment/commands?app=<app_id>\`.
2. **Trigger Build**: Call \`POST /api/deployment/execute\` with \`{"app", "templateId": "build_apk", "flavor": "dev", "confirmed": true}\`.
3. **Process Isolation**: The backend spawns an isolated process group with a dedicated log file and PID, returning \`jobId\`.
4. **Live Log Streaming**: UI polls \`GET /api/deployment/job?id=<job_id>\` to stream live stdout/stderr chunks and timer.

---

## Flow 3: Wireless Testing (Camera QR & Multi-Device ADB Push)
1. **Local Download Server**: Instantly serves compiled \`.apk\` via \`/api/deployment/download/<app>\` with token authorization.
2. **Instant Camera QR**: Generates pure-Python SVG QR code via \`GET /api/deployment/qr?text=<url>\`. Testers scan with their phone camera to download without cables.
3. **Wireless ADB Parallel Push**:
   - Discovers Wi-Fi/USB devices via \`GET /api/deployment/adb/devices\`.
   - Pushes and installs APK in parallel across all selected devices via \`POST /api/deployment/adb/push\`.

---

## Flow 4: Chained Release Pipeline
1. **Sequence**: \`App Doctor Pre-flight\` ➔ \`Flutter Build AppBundle\` ➔ \`Build Size Regression Check\` ➔ \`Upload Google Play\` ➔ \`Slack / Teams Notification\`.
2. **Execution**: Triggered via \`POST /api/deployment/pipelines/run\`.
3. **Fail-Fast Protection**: If any step fails (e.g. keystore expired or uncompressed assets detected), execution aborts immediately to protect store releases.

---

## Flow 5: Inbound CI/CD & Two-Way ChatOps
1. **Slack Slash Command**: Post \`/deploy customer_app prod build_aab\` into Slack.
2. **HMAC Signature Check**: Validates incoming request signature using \`X-Slack-Signature\` or \`X-Hub-Signature-256\`.
3. **Automated Headless Runner**: Dispatches build and posts interactive completion card back to the originating channel.
`
    },
    readme: {
        title: "README — Dev Deployment",
        category: "Repository Docs",
        filename: "README.md",
        content: `# Dev Deployment Console

A zero-dependency, local-first developer dashboard for automating Flutter & mobile builds, Fastlane scripts, diagnostics, and team delivery.

## Key Highlights
- **Zero Third-Party Python Dependencies**: Runs purely on Python standard library (\`http.server\`, \`zipfile\`, \`json\`, \`subprocess\`).
- **Monorepo & Single-App Support**: Auto-detects Flutter apps with or without Melos.
- **Local APK Server & QR Code**: Scan phone camera to download test builds over local Wi-Fi.
- **Pre-flight App Doctor**: Prevents failed 20-minute CI builds by diagnosing environment issues upfront.
- **Build Size Inspector**: Compares APK/AAB size deltas and detects uncompressed assets.
`
    },
    architecture: {
        title: "ARCHITECTURE & Design Decisions",
        category: "Repository Docs",
        filename: "ARCHITECTURE.md",
        content: `# System Architecture & Principles

## 1. Zero External Dependencies (ADR 0001)
No \`pip install\`, no Node.js runtime for backend. Anyone with Python 3.10+ can clone and run immediately via \`./start.sh\`.

## 2. Local-First Execution
All commands are generated as transparent shell / Fastlane commands executed locally under user privileges.

## 3. Tab-Isolated Workspaces (C9)
Every browser tab carries an \`X-Workspace\` header so multiple monorepos can be monitored independently without race conditions.

## 4. Security Guards
- Localhost only (DNS rebinding rejected).
- CSRF Origin check on all mutating endpoints.
- Path traversal sanitization on all artifact and credential downloads.
`
    },
    faq: {
        title: "FAQ & Troubleshooting",
        category: "Repository Docs",
        filename: "FAQ.md",
        content: `# Frequently Asked Questions

### Q: Why do I see "Server Offline" when opening index.html?
A: Web browsers run \`file://\` in a strict sandbox. To communicate with local Flutter projects, start the Python server using \`./start.sh\`.

### Q: How do I scan the QR code from my phone?
A: Make sure your phone is connected to the same Wi-Fi network as your development computer. The console automatically detects your LAN IP (e.g. \`http://192.168.1.50:18112\`).

### Q: How do I configure Slack or Discord webhooks?
A: Open the **Configure** dialog (top right), navigate to the **Notifications** tab, and enter your webhook URL.
`
    },
    api: {
        title: "REST API Documentation (Complete)",
        category: "API Endpoints",
        filename: "docs/API.md",
        content: `# REST API Documentation 🔌

The Dev Deployment Console provides a robust REST API powering both the web UI and external command-line automation scripts. The server listens on \`localhost\` (default port \`18112\`).

---

## Conventions & Security

| Header / Query | Required | Meaning |
|:---|:---|:---|
| \`X-API-Token\` | Required for mutating endpoints | Bearer auth token from \`~/.config/dev-deployment/auth_token.txt\` |
| \`?token=\` or \`?auth=\` | Media / APK streaming | Query parameter fallback for downloading APKs or rendering QR SVGs |
| \`X-Workspace\` | Optional | Absolute directory of target project workspace (defaults to active root) |
| \`Content-Type: application/json\` | POST endpoints | Required for all JSON payloads (except multipart \`.p8\` upload) |

### Security Rules
- **Host Header Validation:** Non-localhost \`Host\` headers (\`127.0.0.1\`, \`localhost\`, LAN IP) are rejected with \`403 DNS Rebinding Rejected\`.
- **CORS Isolation:** Unapproved external browser origins are rejected with \`403 Cross-Origin Request Rejected\` (local \`file://\` / \`Origin: null\` supported).
- **Body Size Limit:** JSON POST bodies exceeding 1 MB are rejected with \`413 Payload Too Large\`.
- **Response Format:** All endpoints return JSON with \`"success": true|false\`. On failure, an informative \`"error"\` message is included.

---

## Workspaces & Projects

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/workspaces\` | – | Returns list of added projects, default workspace, and directory existence check. |
| \`POST\` | \`/api/deployment/workspace/allow\` | \`{"path": "/path/to/project"}\` | Adds a new project workspace to \`config/workspaces_list.json\`. |
| \`POST\` | \`/api/deployment/workspace/remove\` | \`{"path": "/path/to/project"}\` | Removes a project tab from the console list. Returns \`409\` if a job is running. |
| \`GET\` | \`/api/deployment/inspect-path\` | \`?path=/path/to/inspect\` | Inspects arbitrary directory: detects layout, app count, Melos monorepo status, and stack. |
| \`POST\` | \`/api/deployment/pick\` | \`{"kind": "folder"|"file"}\` | Opens OS native folder picker dialog on server host and returns selected path. |
| \`POST\` | \`/api/deployment/workspace/select\` | \`{"path": "/path/to/project"}\` | Sets server-wide default workspace. |

---

## Apps & Configuration

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/apps\` | – | List of detected apps and non-deployable packages: \`id\`, \`name\`, \`path\`, \`stack\`, \`is_package\`, \`version\`. |
| \`POST\` | \`/api/deployment/apps\` | \`{"id", "name", "path", ...}\` | Register or update an application metadata record manually. |
| \`POST\` | \`/api/deployment/rescan-workspace\` | – | Forces full re-detection of applications and packages across the project tree. |
| \`GET\` | \`/api/deployment/deploy-config\` | – | Full deployment configuration object from \`<project>/.dev-dashboard/deploy_config.json\`. |
| \`POST\` | \`/api/deployment/deploy-config/save\` | Full config payload | Validates schema and saves deployment configuration. |
| \`GET\` | \`/api/deployment/scan-config\` | \`?app=<app_id>\` | Runs static code scanner to detect bundle IDs, package names, flavors, and Firebase files for one app. |
| \`POST\` | \`/api/deployment/scan-all\` | \`{"force": true}\` | Runs static auto-scanner across all apps in the active project. |
| \`GET\` | \`/api/deployment/templates\` | – | Retrieves template command definitions grouped by category. |
| \`GET\` | \`/api/deployment/commands\` | \`?app=<app_id>\` | Returns executable command tiles for the specified app and its flavors. |
| \`POST\` | \`/api/deployment/regenerate\` | – | Re-runs command discovery and builds executable parameter maps. |

---

## Job Execution & History

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`POST\` | \`/api/deployment/execute\` | \`{"app", "templateId", "flavor", "confirmed"}\` | Starts asynchronous build job subprocess. Rejects arbitrary commands. |
| \`GET\` | \`/api/deployment/job\` | \`?id=<job_id>\` | Polls job execution state: \`running\`, \`success\`, \`error\`, \`stopped\`, stdout/stderr chunks. |
| \`POST\` | \`/api/deployment/stop\` | \`{"jobId": "<job_id>"}\` | Sends \`SIGTERM\` (followed by \`SIGKILL\`) to terminate active process group. |
| \`GET\` | \`/api/deployment/running-jobs\` | – | Returns list of all currently active jobs across all projects. |
| \`GET\` | \`/api/deployment/history\` | \`?app=&flavor=&status=&limit=50\` | Queries past execution records from \`deployment_history.jsonl\`. |

---

## Server Management & Lifecycle Controls

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/server-status\` | – | Lightweight heartbeat ping returning online status, port, and auth token for local clients. |
| \`GET\` | \`/api/deployment/server/status\` | – | Detailed server telemetry: uptime seconds, PID, memory, active workspace root. |
| \`GET\` | \`/api/deployment/server/service-status\` | – | Detects if desktop shortcut or systemd user service is installed on host. |
| \`POST\` | \`/api/deployment/server/start\` | \`{"port": 18112}\` | Spawns background server process. |
| \`POST\` | \`/api/deployment/server/stop\` | – | Gracefully shuts down active server process. |
| \`POST\` | \`/api/deployment/server/end\` | – | Graceful termination alias for Stop Server. |
| \`POST\` | \`/api/deployment/server/restart\` | – | Triggers automated in-place process restart via \`os.execv\`. |
| \`POST\` | \`/api/deployment/server/install-desktop\` | – | Creates native \`.desktop\` application shortcut in \`~/.local/share/applications/\`. |
| \`POST\` | \`/api/deployment/server/install-service\` | – | Installs and activates systemd user login service \`dev-deployment.service\`. |

---

## Pre-flight Diagnostics (App Doctor)

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/doctor\` | \`?app=<app_id>&flavor=<flavor>\` | Runs 12+ pre-flight diagnostics (Flutter SDK, Android SDK, CocoaPods, keystores, provisioning profiles, Git clean status, Firebase configs). |
| \`GET\` | \`/api/deployment/health\` | – | System-wide toolchain health check (Flutter, Git, Java, Xcode, Fastlane). |

---

## Certificate & Keystore Expiry Sentinel

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/sentinel\` | \`?app=<app_id>&flavor=<flavor>\` | Proactively checks Apple \`.p8\` keys, iOS distribution certs, Android upload keys, and cross-platform Firebase project IDs. |
| \`GET\` | \`/api/deployment/ios-cert-check\` | \`?app=<app_id>&flavor=<flavor>\` | Validates iOS provisioning profiles and distribution certificates. |

---

## Build Size Inspector & Diff

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/build-size\` | \`?jobId=<id>&app=<app>&flavor=<flavor>\` | Inspects ZIP central directory of generated AAB/APK without disk extraction. Compares byte size against previous run and flags uncompressed raw assets (\`ZIP_STORED\` ≥ 500 KB). |

---

## Local APK Hosting & QR Code

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/apk-info\` | \`?app=<app_id>&flavor=<flavor>\` | Locates latest \`.apk\` artifact and returns direct download URL and size. |
| \`GET\` | \`/api/deployment/download/<target>\` | \`?token=<auth_token>\` | Streams generated \`.apk\` file for direct wireless installation. Verified via query token or \`X-API-Token\`. |
| \`GET\` | \`/api/deployment/ipa-info\` | \`?app=<app_id>&flavor=<flavor>\` | Locates latest \`.ipa\` artifact and returns direct download URL and native \`itms-services://\` OTA link. |
| \`GET\` | \`/api/deployment/download-ipa/<target>\` | \`?token=<auth_token>\` | Streams compiled \`.ipa\` binary with chunked range support. |
| \`GET\` | \`/api/deployment/ota/manifest.plist\` | \`?app=<app>&flavor=<flavor>&token=<token>\` | Generates Apple's dynamic XML \`manifest.plist\` for 10-second Camera QR OTA install. |
| \`GET\` | \`/api/deployment/qr\` | \`?text=<url>&token=<auth_token>\` | Generates pure Python SVG QR code representation of the download URL for mobile camera scanning. |

---

## Saved Pipelines (Chained Workflows)

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/pipelines\` | \`?app=<app_id>\` | Returns saved multi-step deployment pipelines for the app. |
| \`POST\` | \`/api/deployment/pipelines/save\` | \`{"app", "pipeline": {"id", "name", "steps": [...]}}\` | Saves or updates a visual pipeline definition. |
| \`POST\` | \`/api/deployment/pipelines/delete\` | \`{"app", "pipelineId": "<id>"}\` | Deletes a saved pipeline definition. |
| \`POST\` | \`/api/deployment/pipelines/run\` | \`{"app", "pipelineId", "flavor", "confirmed"}\` | Triggers sequential step-by-step pipeline execution with stop-on-failure safety. |
| \`GET\` | \`/api/deployment/pipelines/run\` | \`?id=<run_id>\` | Returns live execution progress, active step index, and per-step logs. |
| \`POST\` | \`/api/deployment/pipelines/stop\` | \`{"runId": "<run_id>"}\` | Aborts active pipeline execution and releases the app lock. |

---

## Universal Webhooks & CI/CD Ingestion

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`POST\` | \`/api/deployment/notifications/test\` | \`{"url", "provider", "app"?, ...}\` | Sends immediate test card to any webhook (Slack, Discord, Teams, Google Chat, WhatsApp, etc.). |
| \`POST\` | \`/api/deployment/webhook/incoming\` | JSON or form-urlencoded | Universal incoming webhook ingestion. Triggers commands or automated pipelines from GitHub, GitLab, Slack, or cURL. |
| \`POST\` | \`/api/deployment/webhook/incoming/<provider>\` | \`github\` \| \`gitlab\` \| \`slack\` \| \`generic\` | Provider-specific routing alias with tailored header and payload parsers. |

---

## Credentials & Keys

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/credentials\` | \`?app=<app_id>\` | Returns credential resolution status (Play service account, Apple \`.p8\` key, Issuer UUID). |
| \`POST\` | \`/api/deployment/credentials/scan\` | \`{"folder": "/scan/path"}\` | Deep scans folder for Google Play JSONs, Apple \`.p8\` keys, and Firebase configs. |
| \`POST\` | \`/api/deployment/credentials/import\` | \`{"path", "app"?, "flavor"?, "issuerId"?}\` | Securely copies credential file to \`~/.config/dev-deployment/\` with \`chmod 600\`. |
| \`POST\` | \`/api/deployment/credentials/upload\` | \`{"filename", "contentBase64", ...}\` | Imports uploaded base64 key directly into user keychain directory. |
| \`POST\` | \`/api/deployment/credentials/remove\` | \`{"kind", "app"?}\` | Disassociates key mapping from specified application. |
| \`POST\` | \`/api/deployment/p8/upload\` | Multipart or JSON payload | Uploads App Store Connect PKCS#8 private key file. |

---

## Wireless ADB Device Management & Parallel Push

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/adb/devices\` | – | Discovers connected USB, Wi-Fi, and emulator Android devices via \`adb devices -l\`. |
| \`POST\` | \`/api/deployment/adb/connect\` | \`{"ip": "192.168.1.50", "port": 5555}\` | Pairs wireless device via \`adb connect\`. |
| \`POST\` | \`/api/deployment/adb/disconnect\` | \`{"ip": "192.168.1.50", "port": 5555}\` | Disconnects device via \`adb disconnect\`. |
| \`POST\` | \`/api/deployment/adb/push\` | \`{"app": "...", "deviceIds": ["..."]}\` | Pushes and installs APK in parallel across all selected devices. |

---

## Build Time Profiler & Bottleneck Heatmap

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/build-profile\` | – | Analyzes latest completed job log into 6 mobile phases with bottleneck detection (≥30%). |
| \`GET\` | \`/api/deployment/job/profile\` | \`?job_id=<id>\` | Analyzes compilation timings and phase breakdown for specific historical job. |

---

## Smart Silent Cache Warmer

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/cache-warmer/status\` | – | Returns daemon status (\`idle\`, \`warming\`, \`ready\`), watched branch, and last warm time. |
| \`POST\` | \`/api/deployment/cache-warmer/warm\` | – | Triggers background dependency resolution (\`flutter pub get\`) when no jobs are active. |

---

## Documentation Provider

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/docs/list\` | – | Returns list of all available documentation guides and categories. |
| \`GET\` | \`/api/deployment/docs\` | \`?doc=<id>\` | Returns markdown document content for display in the interactive docs viewer. |
`
    },
    'api-workspaces': {
        title: "Workspaces & App Discovery APIs",
        category: "API Endpoints",
        filename: "docs/API.md#workspaces",
        content: `# Workspaces & App Discovery APIs 📂

Endpoints for managing workspace directories, detecting applications across single repos and Melos monorepos, and configuring project settings.

---

## Endpoints Table

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/workspaces\` | – | Returns list of added projects, default workspace, and directory existence check. |
| \`POST\` | \`/api/deployment/workspace/allow\` | \`{"path": "/path/to/project"}\` | Adds a new project workspace to \`config/workspaces_list.json\`. |
| \`POST\` | \`/api/deployment/workspace/remove\` | \`{"path": "/path/to/project"}\` | Removes a project tab from the console list. Returns \`409\` if a job is running. |
| \`GET\` | \`/api/deployment/inspect-path\` | \`?path=/path/to/inspect\` | Inspects arbitrary directory: detects layout, app count, package count, Melos monorepo status, and framework stack. |
| \`POST\` | \`/api/deployment/pick\` | \`{"kind": "folder"|"file"}\` | Opens OS native folder picker dialog on server host and returns selected path. |
| \`POST\` | \`/api/deployment/workspace/select\` | \`{"path": "/path/to/project"}\` | Sets server-wide default workspace. |
| \`GET\` | \`/api/deployment/apps\` | – | List of detected apps and non-deployable packages: \`id\`, \`name\`, \`path\`, \`stack\`, \`is_package\`, \`version\`, \`icon\`. |
| \`POST\` | \`/api/deployment/apps\` | \`{"id", "name", "path", ...}\` | Register or update an application metadata record manually. |
| \`POST\` | \`/api/deployment/rescan-workspace\` | – | Forces full re-detection of applications and packages across the project tree. |
| \`GET\` | \`/api/deployment/deploy-config\` | – | Full deployment configuration object from \`<project>/.dev-dashboard/deploy_config.json\`. |
| \`POST\` | \`/api/deployment/deploy-config/save\` | Full config payload | Validates schema and saves deployment configuration. |
| \`GET\` | \`/api/deployment/scan-config\` | \`?app=<app_id>\` | Runs static code scanner to detect bundle IDs, package names, flavors, and Firebase files for one app. |
| \`POST\` | \`/api/deployment/scan-all\` | \`{"force": true}\` | Runs static auto-scanner across all apps in the active project. |
| \`GET\` | \`/api/deployment/templates\` | – | Retrieves template command definitions grouped by category. |
| \`GET\` | \`/api/deployment/commands\` | \`?app=<app_id>\` | Returns executable command tiles for the specified app and its flavors. |
| \`POST\` | \`/api/deployment/regenerate\` | – | Re-runs command discovery and builds executable parameter maps. |
`
    },
    'api-execution': {
        title: "Builds, Jobs & Server APIs",
        category: "API Endpoints",
        filename: "docs/API.md#execution",
        content: `# Build Execution, Subprocesses & Server APIs ⚡

Endpoints for executing asynchronous Flutter/Fastlane commands, live terminal streaming, job lifecycle management, chained pipelines, and server daemon controls.

---

## Endpoints Table

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`POST\` | \`/api/deployment/execute\` | \`{"app", "templateId", "flavor", "confirmed"}\` | Starts asynchronous build job subprocess. Rejects arbitrary commands; only pre-verified template actions run. |
| \`GET\` | \`/api/deployment/job\` | \`?id=<job_id>\` | Polls job execution state: \`running\`, \`success\`, \`error\`, \`stopped\`, stdout/stderr chunks, duration. |
| \`POST\` | \`/api/deployment/stop\` | \`{"jobId": "<job_id>"}\` | Sends \`SIGTERM\` (followed by \`SIGKILL\`) to terminate active process group. Releases app busy lock. |
| \`GET\` | \`/api/deployment/running-jobs\` | – | Returns list of all currently active jobs across all projects. |
| \`GET\` | \`/api/deployment/history\` | \`?app=&flavor=&status=&limit=50\` | Queries past execution records from \`<project>/.dev-dashboard/deployment_history.jsonl\`. |
| \`GET\` | \`/api/deployment/pipelines\` | \`?app=<app_id>\` | Returns saved multi-step deployment pipelines for the app. |
| \`POST\` | \`/api/deployment/pipelines/save\` | \`{"app", "pipeline": {"id", "name", "steps": [...]}}\` | Saves or updates a visual pipeline definition. |
| \`POST\` | \`/api/deployment/pipelines/delete\` | \`{"app", "pipelineId": "<id>"}\` | Deletes a saved pipeline definition. |
| \`POST\` | \`/api/deployment/pipelines/run\` | \`{"app", "pipelineId", "flavor", "confirmed"}\` | Triggers sequential step-by-step pipeline execution with stop-on-failure safety. |
| \`GET\` | \`/api/deployment/pipelines/run\` | \`?id=<run_id>\` | Returns live execution progress, active step index, and per-step logs. |
| \`POST\` | \`/api/deployment/pipelines/stop\` | \`{"runId": "<run_id>"}\` | Aborts active pipeline execution and releases the app lock. |
| \`GET\` | \`/api/deployment/server-status\` | – | Lightweight heartbeat ping returning online status, port, and auth token for local clients. |
| \`GET\` | \`/api/deployment/server/status\` | – | Detailed server telemetry: uptime seconds, PID, memory, active workspace root. |
| \`GET\` | \`/api/deployment/server/service-status\` | – | Detects if desktop shortcut or systemd user service is installed on host. |
| \`POST\` | \`/api/deployment/server/start\` | \`{"port": 18112}\` | Spawns background server process. |
| \`POST\` | \`/api/deployment/server/stop\` | – | Gracefully shuts down active server process. |
| \`POST\` | \`/api/deployment/server/end\` | – | Graceful termination alias for Stop Server. |
| \`POST\` | \`/api/deployment/server/restart\` | – | Triggers automated in-place process restart via \`os.execv\`. |
| \`POST\` | \`/api/deployment/server/install-desktop\` | – | Creates native \`.desktop\` application shortcut in \`~/.local/share/applications/\`. |
| \`POST\` | \`/api/deployment/server/install-service\` | – | Installs and activates systemd user login service \`dev-deployment.service\`. |
`
    },
    'api-artifacts': {
        title: "Artifacts, OTA & QR APIs",
        category: "API Endpoints",
        filename: "docs/API.md#artifacts",
        content: `# Artifact Hosting, Dynamic Apple OTA Plists & QR Codes 📱

Endpoints for hosting compiled APK and IPA binaries locally, streaming downloads with Range support, and generating wireless installation QR codes.

---

## Endpoints Table

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/apk-info\` | \`?app=<app_id>&flavor=<flavor>\` | Locates latest \`.apk\` artifact and returns direct download URL and size. |
| \`GET\` | \`/api/deployment/download/<target>\` | \`?token=<auth_token>\` | Streams generated \`.apk\` file for direct wireless installation. Verified via query token or \`X-API-Token\`. |
| \`GET\` | \`/api/deployment/ipa-info\` | \`?app=<app_id>&flavor=<flavor>\` | Locates latest \`.ipa\` artifact and returns direct download URL and native \`itms-services://\` OTA link. |
| \`GET\` | \`/api/deployment/download-ipa/<target>\` | \`?token=<auth_token>\` | Streams compiled \`.ipa\` binary with chunked range support. |
| \`GET\` | \`/api/deployment/ota/manifest.plist\` | \`?app=<app>&flavor=<flavor>&token=<token>\` | Generates Apple's dynamic XML \`manifest.plist\` for 10-second Camera QR OTA install. |
| \`GET\` | \`/api/deployment/qr\` | \`?text=<url>&token=<auth_token>\` | Generates pure Python SVG QR code representation of the download URL for mobile camera scanning. |
`
    },
    'api-diagnostics': {
        title: "Doctor, Sentinel & Size APIs",
        category: "API Endpoints",
        filename: "docs/API.md#diagnostics",
        content: `# Pre-flight Diagnostics, Sentinel & Build Size Inspector 🩺

Comprehensive pre-flight checks, proactive expiration warnings for keystores/certificates, and deep in-memory ZIP central directory diffing.

---

## Endpoints Table

| Method | Endpoint | Query Parameters | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/doctor\` | \`?app=<app_id>&flavor=<flavor>\` | Runs 12+ pre-flight diagnostics (Flutter SDK, Android SDK, CocoaPods, keystores, provisioning profiles, Git clean status, Firebase configs). |
| \`GET\` | \`/api/deployment/health\` | – | System-wide toolchain health check (Flutter, Git, Java, Xcode, Fastlane). |
| \`GET\` | \`/api/deployment/sentinel\` | \`?app=<app_id>&flavor=<flavor>\` | Proactively checks Apple \`.p8\` keys, iOS distribution certs, Android upload keys, and cross-platform Firebase project IDs. |
| \`GET\` | \`/api/deployment/ios-cert-check\` | \`?app=<app_id>&flavor=<flavor>\` | Validates iOS provisioning profiles and distribution certificates. |
| \`GET\` | \`/api/deployment/build-size\` | \`?jobId=<id>&app=<app>&flavor=<flavor>\` | Inspects ZIP central directory of generated AAB/APK without disk extraction. Compares byte size against previous run and flags uncompressed raw assets (\`ZIP_STORED\` ≥ 500 KB). |
`
    },
    'api-webhooks': {
        title: "Webhooks & CI/CD Ingestion APIs",
        category: "API Endpoints",
        filename: "docs/API.md#webhooks",
        content: `# Universal Webhooks & CI/CD Ingestion Gateway 🔔

Multi-provider notifications (Slack, Discord, Microsoft Teams, Google Chat, WhatsApp) and universal incoming CI/CD triggers.

---

## Endpoints Table

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`POST\` | \`/api/deployment/notifications/test\` | \`{"url", "provider", "app"?, "custom_template"?, "custom_headers"?, "phone"?}\` | Sends immediate test card to any webhook (Slack, Discord, Teams, Google Chat, WhatsApp, Custom template, or Generic JSON). |
| \`POST\` | \`/api/deployment/webhook/incoming\` | JSON or form-urlencoded | Universal incoming webhook ingestion. Triggers commands or automated pipelines from GitHub, GitLab, Slack, or cURL. |
| \`POST\` | \`/api/deployment/webhook/incoming/<provider>\` | \`github\` \| \`gitlab\` \| \`slack\` \| \`generic\` | Provider-specific routing alias with tailored header and payload parsers. |
| \`POST\` | \`/api/deployment/webhook\` | \`{"app", "templateId", "flavor"}\` | Legacy endpoint maintained for backward compatibility. |
| \`GET\` | \`/api/deployment/credentials\` | \`?app=<app_id>\` | Returns credential resolution status (Play service account, Apple \`.p8\` key, Issuer UUID). Never returns private secrets. |
| \`POST\` | \`/api/deployment/credentials/scan\` | \`{"folder": "/scan/path"}\` | Deep scans folder for Google Play JSONs, Apple \`.p8\` keys, and Firebase configs by file content analysis. |
| \`POST\` | \`/api/deployment/credentials/import\` | \`{"path", "app"?, "flavor"?, "issuerId"?}\` | Securely copies credential file to \`~/.config/dev-deployment/\` with \`chmod 600\`. |
| \`POST\` | \`/api/deployment/credentials/upload\` | \`{"filename", "contentBase64", ...}\` | Imports uploaded base64 key directly into user keychain directory. |
| \`POST\` | \`/api/deployment/credentials/remove\` | \`{"kind", "app"?}\` | Disassociates key mapping from specified application. |
| \`POST\` | \`/api/deployment/p8/upload\` | Multipart or JSON payload | Uploads App Store Connect PKCS#8 private key file. |
`
    },
    'api-innovations': {
        title: "Wireless ADB, Profiler & Warmer APIs",
        category: "API Endpoints",
        filename: "docs/API.md#innovations",
        content: `# Mobile Innovations: Wireless ADB, Profiler & Cache Warmer 📱

Innovative automation tools for wireless Android debugging and installation, build bottleneck analysis, and silent dependency pre-fetching.

---

## Endpoints Table

| Method | Endpoint | Query / Body | Returns / Purpose |
|:---|:---|:---|:---|
| \`GET\` | \`/api/deployment/adb/devices\` | – | Discovers connected USB, Wi-Fi, and emulator Android devices via \`adb devices -l\`. |
| \`POST\` | \`/api/deployment/adb/connect\` | \`{"ip": "192.168.1.50", "port": 5555}\` | Pairs wireless device via \`adb connect\`. |
| \`POST\` | \`/api/deployment/adb/disconnect\` | \`{"ip": "192.168.1.50", "port": 5555}\` | Disconnects device via \`adb disconnect\`. |
| \`POST\` | \`/api/deployment/adb/push\` | \`{"app": "...", "deviceIds": ["..."]}\` | Pushes and installs APK in parallel across all selected devices. |
| \`GET\` | \`/api/deployment/build-profile\` | – | Analyzes latest completed job log into 6 mobile phases with bottleneck detection (≥30%). |
| \`GET\` | \`/api/deployment/job/profile\` | \`?job_id=<id>\` | Analyzes compilation timings and phase breakdown for specific historical job. |
| \`GET\` | \`/api/deployment/cache-warmer/status\` | – | Returns daemon status (\`idle\`, \`warming\`, \`ready\`), watched branch, and last warm time. |
| \`POST\` | \`/api/deployment/cache-warmer/warm\` | – | Triggers background dependency resolution (\`flutter pub get\`) when no jobs are active. |
| \`GET\` | \`/api/deployment/github/status\` | – | Returns GitHub Actions hybrid cloud integration status and token presence. |
| \`POST\` | \`/api/deployment/github/config\` | \`{"token", "repo", "workflow"}\` | Configures GitHub Actions repository and remote workflow parameters. |
| \`POST\` | \`/api/deployment/github/install-template\` | – | Installs starter \`.github/workflows/deploy.yml\` into repository. |
| \`POST\` | \`/api/deployment/github/dispatch\` | \`{"app", "flavor", "workflow"}\` | Triggers remote GitHub Actions build workflow via dispatch API. |
`
    },
    pipelines: {
        title: "Pipelines Proposal (ADR 0001)",
        category: "Proposals & ADRs",
        filename: "0001-pipelines.md",
        content: `# 🔀 Saved Pipelines Architecture (ADR 0001)

Saved Pipelines chain multi-step build, verification, and release steps into a single 1-click execution flow.

---

## ⚡ Core Concepts
- **Sequential Execution**: Steps execute one after another in order.
- **Fail-Fast Safety**: If a step fails, the pipeline aborts immediately to prevent uploading corrupted builds.
- **Step Templates**: Mix pre-configured templates (\`flutter build appbundle\`, \`fastlane android upload_aab\`) with custom shell commands.
- **Visual Progress**: Each step card updates with spinning, pass, or fail states in real time.
`
    },
    changelog: {
        title: "CHANGELOG & Release Notes",
        category: "Repository Docs",
        filename: "CHANGELOG.md",
        content: `# 📋 CHANGELOG & Feature Highlights

## Recent Milestones:
- **Documentation & Knowledge Hub**: Built-in markdown documentation viewer and offline quickstart guide.
- **Local APK Hosting & QR Code**: Serve debug/QA builds over local HTTP with instant phone camera install.
- **Outgoing Webhooks**: Automated notifications for Slack, Discord, and Microsoft Teams.
- **Certificate & Keystore Sentinel**: Proactive expiry warnings for Apple .p8 keys and Android upload keystores.
- **Build Size Inspector & Diff**: Instant APK/AAB size regression alerts and uncompressed assets detector.
`
    },
    installing: {
        title: "Installation & Setup Guide",
        category: "Getting Started",
        filename: "docs/INSTALLING.md",
        content: `# 🛠️ Installation & Setup Guide

The Dev Deployment Console is a zero-dependency, local-first developer tool running directly on Python ≥ 3.10 without \`pip\` or \`npm\`.

---

## ⚡ Quickstart
\`\`\`bash
# 1. Clone & enter repository
git clone https://github.com/sunilbvb/dev-deployment.git
cd dev-deployment

# 2. Launch Console
./start.sh
\`\`\`
The script validates Python ≥ 3.10, creates a bearer auth token, and opens the console in your default browser.

---

## 💻 1-Click Launchers
- **Linux Desktop Launcher**: Installs native desktop shortcut in \`~/.local/share/applications/\`.
- **Systemd User Service**: Launches automatically on login as a background user daemon (\`dev-deployment.service\`).
`
    },
    requirements: {
        title: "System Requirements & Prerequisites",
        category: "Getting Started",
        filename: "docs/REQUIREMENTS.md",
        content: `# 📋 System Requirements & Prerequisites

## 💻 Host Requirements
- **CPU**: 2 cores minimum (4+ cores recommended for Flutter/native builds).
- **RAM**: 512 MB for console runtime (8 GB+ recommended for builds).
- **Disk**: 50 MB for console code.
- **Python**: **Python ≥ 3.10** (standard library only).
- **Browser**: Chrome 90+, Edge 90+, Firefox 90+, Safari 15+.

## 🛠️ Optional Build Tools
- **Flutter SDK**: ≥ 3.0.0 (for Flutter apps).
- **Android Platform Tools**: \`adb\` (for wireless device push).
- **Fastlane**: For automated Google Play and Apple App Store distribution.
`
    },
    'use-cases': {
        title: "Real-World Use Cases & Workflows",
        category: "Getting Started",
        filename: "docs/USE_CASES.md",
        content: `# 💡 Real-World Use Cases & Workflows

## 1. Solo Mobile Developers
1-click build cards for Dev, QA, and Prod. Instant camera QR scan to install debug APKs directly onto test phones without cables.

## 2. QA & Test Automation Teams
Wireless ADB pairing detects all Wi-Fi Android devices and pushes updated APKs in parallel to 5+ phones simultaneously in seconds.

## 3. Agency & White-Label Monorepos
Manage multiple client brands in a single Melos monorepo. Switching app cards auto-configures respective Fastlane lanes and keystores.

## 4. Headless CI/CD & ChatOps
Trigger builds directly from Slack slash commands (\`/deploy app prod\`) or GitHub webhooks with HMAC SHA-256 signature verification.
`
    },
    features: {
        title: "Complete Features Catalog",
        category: "Platform & Tools",
        filename: "docs/FEATURES.md",
        content: `# ⚡ Complete Features Catalog

## 🧭 Workspaces & Builds
- **Melos & Multi-App Discovery**: Auto-detects Flutter monorepos and packages.
- **Environment Tabs**: Dev, QA, and Prod build cards with production confirmation safeguards.
- **Live Output Streaming**: Subprocess execution with live stdout/stderr chunks and timer.

## 🔍 Pre-flight App Doctor
- **1-Click System Check**: Evaluates 12+ environment prerequisites in <2 seconds.
- **Keystore & Git Validation**: Verifies release keystores and warns on uncommitted changes.

## 📦 Binary Packaging & Delivery
- **Local APK & Camera QR**: Streams \`.apk\` files with Reed-Solomon SVG QR codes.
- **iOS OTA IPA Hosting**: Dynamic XML \`manifest.plist\` for wireless iPhone camera install.
- **Build Size Central Directory Inspector**: Detects uncompressed raw assets (\`ZIP_STORED\` ≥ 500 KB).
- **Certificate Sentinel**: Proactive expiry warnings for Apple \`.p8\` keys and keystores.

## 📱 Mobile Innovations
- **Wireless ADB Manager**: Pairs Wi-Fi devices and installs APKs in parallel.
- **Build Time Profiler**: Surfaces compile bottlenecks with phase heatmaps.
- **Smart Silent Cache Warmer**: Pre-fetches dependencies (\`flutter pub get\`) on Git branch switches.
`
    },
    platforms: {
        title: "Supported Platforms & Ecosystems",
        category: "Platform & Tools",
        filename: "docs/PLATFORMS.md",
        content: `# 📱 Supported Platforms & Ecosystems

## 🎯 Target Mobile OS
- **Android**: Universal APK (\`.apk\`), Android App Bundle (\`.aab\`), Google Play Tracks.
- **iOS & iPadOS**: \`.ipa\` archives, dynamic \`itms-services://\` OTA installs, TestFlight, and App Store.

## 🏗️ Project Layouts
- **Melos Monorepos**: First-class multi-package support.
- **Dart Pub Workspaces**: First-class support.
- **Single-App Flutter**: Pure native detection.

## 🖥️ Host Systems
- **Linux**: Ubuntu, Debian, Fedora, Arch, CentOS.
- **macOS**: Apple Silicon (M1-M4) & Intel x86_64.
- **Windows**: Windows 10/11 via WSL2 or native Python.
`
    },
    dependencies: {
        title: "Dependencies & Runtime Architecture",
        category: "Platform & Tools",
        filename: "docs/DEPENDENCIES.md",
        content: `# 📦 Dependencies & Runtime Architecture

## 🐍 100% Python Standard Library
- **Zero \`pip\` requirements**: No external packages installed.
- **Modules Used**: \`http.server\`, \`urllib\`, \`json\`, \`subprocess\`, \`threading\`, \`hmac\`, \`hashlib\`, \`zipfile\`, \`secrets\`.

## 🌐 Vanilla JavaScript Frontend
- **Zero build step**: Plain ES6+ JS, CSS3, and HTML5.
- **No npm / bundlers**: Pure browser runtime with Lucide SVG icons.

## 🛠️ System Tools (Invoked on demand)
- \`flutter\`, \`adb\`, \`fastlane\`, \`keytool\`, \`git\`.
`
    },
    versions: {
        title: "Versions & Compatibility Matrix",
        category: "Platform & Tools",
        filename: "docs/VERSIONS.md",
        content: `# 🏷️ Versions & Compatibility Matrix

## 📅 Release Milestones
- **v2.4.0 (Current)**: Wireless ADB, Profiler, Cache Warmer, GitHub Actions, Embedded API Hub.
- **v2.3.0**: Universal Webhooks, Local APK QR, iOS OTA Manifest, Sentinel Expiry Monitor.
- **v2.2.0**: Build Size Central Directory Inspector, Pre-flight Doctor Diagnostics.
- **v2.1.0**: Saved Pipelines Chained Automation, Fastlane Parameter Maps.
- **v2.0.0**: Melos Monorepo & Dart Pub Multi-App Workspace Architecture.

## 🧩 Compatibility
- **Python**: 3.10, 3.11, 3.12, 3.13, 3.14+
- **Flutter**: 3.0+ through 3.24+ / 3.27+
- **Android SDK**: API 21 through 35
- **Xcode**: 14.x, 15.x, 16.x
`
    },
    contributing: {
        title: "CONTRIBUTING Guide",
        category: "Guidelines",
        filename: "CONTRIBUTING.md",
        content: `# 🤝 Contributing to Dev Deployment Console

Thanks for helping! Bug fixes, features, docs, and UI polish are welcome.

## 🏁 Development Setup
\`\`\`bash
git clone https://github.com/sunilbvb/dev-deployment.git
cd dev-deployment
./start.sh
\`\`\`

## 📋 Architectural Standards
1. **Zero External Dependencies**: Must run 100% on Python standard library. Never add pip requirements.
2. **Generic Workspaces**: Never hardcode app paths; inspect dynamically via \`X-Workspace\`.
3. **Living Documentation**: Always update \`docs/API.md\`, \`FAQ.md\`, and \`README.md\` with any changes.
4. **All Tests Green**: Run \`python3 -m unittest discover tests\` before submitting PRs.
`
    },
    license: {
        title: "Open Source License (MIT)",
        category: "Repository Docs",
        filename: "LICENSE",
        content: `# MIT License

Copyright (c) 2026 Sunil Bakale and Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
`
    },
    owner: {
        title: "Project Owner, Maintainers & Governance",
        category: "Repository Docs",
        filename: "docs/OWNER.md",
        content: `# 👤 Project Owner, Maintainers & Governance

## 👨‍💻 Project Owner & Lead Architect
- **Owner**: Sunil Bakale
- **GitHub**: [@sunilbvb](https://github.com/sunilbvb)
- **Repository**: [https://github.com/sunilbvb/dev-deployment](https://github.com/sunilbvb/dev-deployment)
- **Role**: System architecture, core Python standard library runtime, and UI design governance.

## 👥 Community
Open-source developer tool licensed under the **MIT License**.
Contributions, issues, and discussions are managed via GitHub.
`
    },
    security: {
        title: "SECURITY Policy & Architecture",
        category: "Guidelines",
        filename: "SECURITY.md",
        content: `# 🔒 SECURITY Policy & Architectural Controls

## Security Model:
- **Zero External Dependencies**: Pure Python standard library backend (\`http.server\`, \`hmac\`, \`secrets\`).
- **Bearer Token Auth**: All mutating API endpoints require valid \`X-API-Token\` generated on startup.
- **Host & Rebinding Protection**: Validates \`Host\` and \`Origin\` headers to reject DNS rebinding attacks.
- **Path Traversal Guards**: Strictly enforces resolved canonical paths within allowed workspace boundaries.
`
    }
};

function formatMethodBadge(cellText) {
    if (!cellText) return '';
    return cellText
        .replace(/<code[^>]*>\s*GET\s*<\/code>/gi, '<span class="ui-badge ui-badge-info" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3);">GET</span>')
        .replace(/<code[^>]*>\s*POST\s*<\/code>/gi, '<span class="ui-badge ui-badge-success" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(34,197,94,0.15); color:#4ade80; border:1px solid rgba(34,197,94,0.3);">POST</span>')
        .replace(/<code[^>]*>\s*DELETE\s*<\/code>/gi, '<span class="ui-badge ui-badge-danger" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3);">DELETE</span>')
        .replace(/<code[^>]*>\s*(PUT|PATCH)\s*<\/code>/gi, '<span class="ui-badge ui-badge-warning" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.3);">$1</span>')
        .replace(/\bGET\b/g, '<span class="ui-badge ui-badge-info" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3);">GET</span>')
        .replace(/\bPOST\b/g, '<span class="ui-badge ui-badge-success" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(34,197,94,0.15); color:#4ade80; border:1px solid rgba(34,197,94,0.3);">POST</span>')
        .replace(/\bDELETE\b/g, '<span class="ui-badge ui-badge-danger" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3);">DELETE</span>')
        .replace(/\b(PUT|PATCH)\b/g, '<span class="ui-badge ui-badge-warning" style="font-weight:700; font-size:0.75rem; padding:2px 8px; border-radius:4px; background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.3);">$1</span>');
}

function renderSimpleMarkdown(md) {
    if (!md) return '';
    let html = escapeHtml(md);

    // Fenced code blocks ```lang ... ```
    html = html.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (_, lang, code) => {
        const langLabel = lang ? `<span style="font-size:0.7rem; text-transform:uppercase; opacity:0.6; margin-bottom:4px; display:block;">${lang}</span>` : '';
        return `<div class="code-block-container" style="background:#0f172a; padding:12px 14px; border-radius:8px; margin:12px 0; border:1px solid rgba(255,255,255,0.08); font-family:monospace; font-size:0.82rem; overflow-x:auto;">${langLabel}<pre style="margin:0; color:#e2e8f0; white-space:pre-wrap;">${code}</pre></div>`;
    });

    // Inline code `...`
    html = html.replace(/`([^`\n]+)`/g, '<code style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-family:monospace; font-size:0.85em; color:var(--ui-primary, #6366f1);">$1</code>');

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h4 style="font-size:1.05rem; font-weight:700; margin:16px 0 6px; color:var(--ui-text-primary);">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="font-size:1.25rem; font-weight:700; margin:22px 0 10px; border-bottom:1px solid var(--ui-border-color); padding-bottom:6px; color:var(--ui-text-primary);">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 style="font-size:1.5rem; font-weight:800; margin:0 0 14px; color:var(--ui-text-primary);">$1</h2>');

    // Horizontal Rules
    html = html.replace(/^---$/gim, '<hr style="border:0; border-top:1px solid var(--ui-border-color); margin:18px 0;">');

    // Bold & Italics
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Links [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--ui-primary, #6366f1); text-decoration:underline;">$1</a>');

    // Unordered lists
    html = html.replace(/^\s*-\s+(.*$)/gim, '<li style="margin:4px 0;">$1</li>');
    html = html.replace(/(<li style="margin:4px 0;">.*<\/li>\s*)+/g, '<ul style="padding-left:20px; margin:8px 0 12px;">$&</ul>');

    // Blockquotes
    html = html.replace(/^>\s+(.*$)/gim, '<blockquote style="border-left:4px solid var(--ui-primary, #6366f1); padding:8px 14px; margin:12px 0; background:rgba(99,102,241,0.06); border-radius:0 6px 6px 0; font-size:0.85rem;">$1</blockquote>');

    // Markdown Tables
    html = html.replace(/((?:^|\n)\|[^\n]+\|\s*\r?\n\|[\s:\-|]+\|\s*\r?\n(?:\|[^\n]+\|\s*(?:\r?\n|$))+)/g, (tableBlock) => {
        const lines = tableBlock.trim().split('\n').map(l => l.trim()).filter(l => l.startsWith('|') && l.endsWith('|'));
        if (lines.length < 2) return tableBlock;

        const parseRow = (line) => line.slice(1, -1).split('|').map(c => c.trim());
        const headerCells = parseRow(lines[0]);
        const bodyLines = lines.slice(2);

        const ths = headerCells.map(h => `<th style="padding:10px 14px; font-weight:600; text-align:left; border-bottom:1px solid var(--ui-border-color); color:var(--ui-text-primary); white-space:nowrap; background:rgba(255,255,255,0.02);">${h}</th>`).join('');

        const trs = bodyLines.map(rowLine => {
            const cells = parseRow(rowLine);
            const tds = cells.map((cell, idx) => {
                let formatted = cell;
                if (idx === 0 || /^(GET|POST|DELETE|PUT|PATCH)$/i.test(cell.trim()) || /<code[^>]*>\s*(GET|POST|DELETE|PUT|PATCH)\s*<\/code>/i.test(cell)) {
                    formatted = formatMethodBadge(cell);
                }
                return `<td style="padding:10px 14px; border-bottom:1px solid rgba(255,255,255,0.05); color:var(--ui-text-secondary); vertical-align:top;">${formatted}</td>`;
            }).join('');
            return `<tr style="transition: background 0.15s ease;">${tds}</tr>`;
        }).join('\n');

        return `\n\n<div class="table-responsive" style="overflow-x:auto; margin:16px 0; border:1px solid var(--ui-border-color); border-radius:8px; background:rgba(0,0,0,0.18);"><table class="ui-table" style="width:100%; border-collapse:collapse; font-size:0.875rem;"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table></div>\n\n`;
    });

    // Paragraphs (lines separated by double breaks)
    return html.split(/\n\n+/).map(p => {
        p = p.trim();
        if (!p) return '';
        if (p.startsWith('<h') || p.startsWith('<div') || p.startsWith('<ul') || p.startsWith('<hr') || p.startsWith('<blockquote') || p.startsWith('<table')) {
            return p;
        }
        return `<p style="margin:8px 0; line-height:1.6;">${p.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');
}

function filterDocsContent(query) {
    if (!els.docsContentArea) return;
    const q = (query || '').toLowerCase().trim();
    const tables = els.docsContentArea.querySelectorAll('.ui-table');
    const sections = els.docsContentArea.querySelectorAll('h2, h3, h4, p, ul, blockquote');

    if (!q) {
        els.docsContentArea.querySelectorAll('tr').forEach(tr => tr.style.display = '');
        els.docsContentArea.querySelectorAll('.table-responsive').forEach(tb => tb.style.display = '');
        sections.forEach(s => s.style.display = '');
        return;
    }

    // Filter table rows
    tables.forEach(table => {
        let visibleCount = 0;
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(tr => {
            const text = tr.textContent.toLowerCase();
            if (text.includes(q)) {
                tr.style.display = '';
                visibleCount++;
            } else {
                tr.style.display = 'none';
            }
        });
        const wrapper = table.closest('.table-responsive');
        if (wrapper) {
            wrapper.style.display = visibleCount > 0 ? '' : 'none';
        }
    });

    // Also filter paragraphs / lists if no tables exist
    if (tables.length === 0) {
        sections.forEach(s => {
            const text = s.textContent.toLowerCase();
            s.style.display = text.includes(q) ? '' : 'none';
        });
    }
}

async function openDocsModal(docId = 'overview') {
    state.activeDocId = docId;
    if (els.docsModalOverlay) {
        els.docsModalOverlay.classList.add('ui-active');
    }
    await loadDoc(docId);
    refreshIcons();
}

function closeDocsModal() {
    if (els.docsModalOverlay) {
        els.docsModalOverlay.classList.remove('ui-active');
    }
}

async function loadDoc(docId) {
    state.activeDocId = docId;

    // Update active state in sidebar
    if (els.docsModalOverlay) {
        els.docsModalOverlay.querySelectorAll('.docs-nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-doc') === docId);
        });
    }

    if (els.docsContentArea) {
        els.docsContentArea.innerHTML = '<div style="padding:20px; color:var(--ui-muted); text-align:center;">Loading document...</div>';
    }

    // Check if pre-rendered HTML section exists in index.html embedded catalog
    const embeddedSec = document.querySelector(`#embeddedDocsCatalog [data-doc="${docId}"]`);
    if (embeddedSec) {
        const cat = embeddedSec.getAttribute('data-category') || 'Documentation';
        const title = embeddedSec.getAttribute('data-title') || docId;
        const filename = embeddedSec.getAttribute('data-filename') || `${docId}.md`;

        if (els.docsCurrentTitle) els.docsCurrentTitle.textContent = title;
        if (els.docsCurrentCategory) els.docsCurrentCategory.textContent = cat;
        if (els.docsCurrentFilename) els.docsCurrentFilename.textContent = filename;
        if (els.docsFooterPath) els.docsFooterPath.textContent = `index.html > #${docId}`;
        if (els.docsContentArea) {
            els.docsContentArea.innerHTML = embeddedSec.innerHTML;
            if (els.docsFilterInput && els.docsFilterInput.value) {
                filterDocsContent(els.docsFilterInput.value);
            }
        }
        refreshIcons();
        return;
    }

    let docData = state.cachedDocs[docId];

    if (!docData) {
        try {
            const res = await fetch(api(`/api/deployment/docs?doc=${encodeURIComponent(docId)}`));
            const data = await res.json();
            if (data.success && data.content) {
                docData = data;
                state.cachedDocs[docId] = data;
            }
        } catch (_) {
            // Server offline or fetch failed - fall back to embedded docs
        }
    }

    if (!docData) {
        docData = DEFAULT_EMBEDDED_DOCS[docId] || DEFAULT_EMBEDDED_DOCS['overview'];
    }

    if (els.docsCurrentTitle) els.docsCurrentTitle.textContent = docData.title || docId;
    if (els.docsCurrentCategory) els.docsCurrentCategory.textContent = docData.category || 'Documentation';
    if (els.docsCurrentFilename) els.docsCurrentFilename.textContent = docData.filename || `${docId}.md`;
    if (els.docsFooterPath) els.docsFooterPath.textContent = docData.filePath || `Doc: ${docData.filename || docId}`;

    if (els.docsContentArea) {
        els.docsContentArea.innerHTML = renderSimpleMarkdown(docData.content);
        if (els.docsFilterInput && els.docsFilterInput.value) {
            filterDocsContent(els.docsFilterInput.value);
        }
    }
    refreshIcons();
}

// Wire Event Listeners
if (els.openDocsBtn) {
    els.openDocsBtn.addEventListener('click', () => openDocsModal('overview'));
}
if (els.bannerOpenDocsBtn) {
    els.bannerOpenDocsBtn.addEventListener('click', () => openDocsModal('overview'));
}
if (els.closeDocsModalBtn) {
    els.closeDocsModalBtn.addEventListener('click', closeDocsModal);
}
if (els.closeDocsBtn) {
    els.closeDocsBtn.addEventListener('click', closeDocsModal);
}
if (els.docsFilterInput) {
    els.docsFilterInput.addEventListener('input', (e) => filterDocsContent(e.target.value));
}
if (els.docsModalOverlay) {
    els.docsModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.docsModalOverlay) closeDocsModal();
        const navBtn = e.target.closest('.docs-nav-item');
        if (navBtn) {
            loadDoc(navBtn.getAttribute('data-doc'));
        }
    });
}

// Top Console Quick Navigation Bar Links
function wireConsoleTopNav() {
    const bind = (id, fn) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', fn);
    };

    bind('navLinkPlayground', () => {
        if (typeof startDemoMode === 'function') {
            startDemoMode();
        } else if (typeof showToast === 'function') {
            showToast('Launching interactive playground demo...');
        }
    });

    bind('navLinkDocs', () => openDocsModal('overview'));

    bind('navLinkServerSetup', () => {
        if (typeof openServerConsoleModal === 'function') {
            openServerConsoleModal();
        } else if (els.serverStatusBadge) {
            els.serverStatusBadge.click();
        }
    });

    bind('navLinkArchitecture', () => openDocsModal('architecture'));
    bind('navLinkApi', () => openDocsModal('api'));
    bind('navLinkExamples', () => openDocsModal('examples'));

    bind('navLinkDoctor', () => {
        if (typeof openDoctorModal === 'function') {
            openDoctorModal(state.selectedApp);
        } else if (els.openDoctorBtn) {
            els.openDoctorBtn.click();
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireConsoleTopNav);
} else {
    wireConsoleTopNav();
}

// Window exports
window.DEFAULT_EMBEDDED_DOCS = DEFAULT_EMBEDDED_DOCS;
window.renderSimpleMarkdown = renderSimpleMarkdown;
window.openDocsModal = openDocsModal;
window.closeDocsModal = closeDocsModal;
window.loadDoc = loadDoc;
window.filterDocsContent = filterDocsContent;
window.wireConsoleTopNav = wireConsoleTopNav;
