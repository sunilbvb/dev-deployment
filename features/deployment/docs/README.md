# 🚀 Deployment Console — Architecture & Reference Manual

> **Location:** `features/deployment/`
> **Backend:** `features/deployment/backend/router.py` & `features/deployment/backend/server.py`
> **Frontend:** `features/deployment/frontend/{index.html, app.js, setup.js, styles.css}`
> **Port:** Configured via `DEPLOYMENT_PORT` (default: `18112`)

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Directory Structure](#directory-structure)
4. [Multi-Stack App Autodiscovery](#multi-stack-app-autodiscovery)
5. [Execution & Job Lifecycle](#execution--job-lifecycle)
6. [Safety & Approval Gates](#safety--approval-gates)
7. [Script & Build Automation Layer](#script--build-automation-layer)
8. [Chat & Notification Integration](#chat--notification-integration)
9. [Deployment History](#deployment-history)
10. [REST API Reference](#rest-api-reference)
11. [Configuration Files](#configuration-files)

---

## Overview

The **Deployment Console** is an open, cross-platform build orchestration dashboard and automation engine. It enables software teams to build, sign, and deploy mobile and web applications (Flutter, React Native, native Android, native iOS, Node.js, and custom shell scripts) through an intuitive browser interface or automated REST endpoints.

### Key Capabilities
- **Platform Agnostic:** Supports Flutter, React Native, Android Gradle, iOS Xcode/Fastlane, and Node/npm pipelines out of the box.
- **Real-Time Streaming:** Streams compilation and deployment logs directly to an in-browser console.
- **Zero Committed Secrets:** Supports ephemeral, in-memory credential loading (macOS Keychain, environment variables, or local `.env` files).
- **Concurrency Protection:** Per-app execution mutex locks prevent collisions when multiple builds are triggered.
- **Production Approval Gate:** Explicit confirmation modals prevent accidental releases to production app stores.
- **Automated Chat Notifications:** Sends formatted cards with build summaries, commit messages, and artifact links to Google Chat or any compatible webhook.

---

## System Architecture

The Deployment Console follows a modular design separating the user interface, backend routing engine, and underlying build scripts:

```
┌─────────────────────────────────────────────────────────────┐
│                       Browser Client                        │
│             features/deployment/frontend/index.html         │
│               (Vanilla JS: app.js, setup.js)                │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / REST
┌──────────────────────────────▼──────────────────────────────┐
│                    Python HTTP Server                       │
│             features/deployment/backend/server.py           │
│                           :18112                            │
└──────────────────────────────┬──────────────────────────────┘
                               │ Direct function calls
┌──────────────────────────────▼──────────────────────────────┐
│                    Router & Process Engine                  │
│             features/deployment/backend/router.py           │
│  - App autodiscovery         - Job state management         │
│  - Command generator         - Concurrency locking          │
│  - Subprocess runner         - Log buffer & history writer  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Subprocess execution
┌──────────────────────────────▼──────────────────────────────┐
│                     Bash Script Engine                      │
│             features/deployment/scripts/                    │
│  - run_build.sh (entry)      - json_utils.sh (helpers)      │
│  - android/ (build & upload) - ios/ (build & upload)        │
│  - chat/ (notifications)     - build_secrets.sh (keychain)  │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
features/deployment/
├── backend/
│   ├── router.py             # Core backend engine (discovery, execution, history)
│   └── server.py             # HTTP server handling routing, CORS, and static files
├── bin/
│   ├── start-deployment.sh   # Background launcher script
│   ├── stop-deployment.sh    # Process stopper with graceful kill
│   ├── restart-deployment.sh # Clean restarter
│   └── status-deployment.sh  # Process status checker
├── docs/
│   └── README.md             # This architecture and reference manual
├── fastlane/
│   └── Gemfile               # Self-contained Fastlane dependency definition
├── frontend/
│   ├── index.html            # Main dashboard user interface
│   ├── app.js                # App selection, execution, polling, and log streaming
│   ├── setup.js              # Build profile management and settings modal
│   └── styles.css            # Dark/light theme styles
└── scripts/
    ├── run_build.sh          # Primary bash command dispatcher
    ├── json_utils.sh         # Helper functions for profile parsing and env loading
    ├── build_profiles.json   # Build profile definitions (flavors, targets)
    ├── build_secrets.sh      # In-memory secret loading from Keychain
    ├── setup_keychain.sh     # Interactive helper for Keychain secrets setup
    ├── android/
    │   ├── android_utils.sh  # AAB/APK build and Google Play Store upload
    │   └── android_diagnostics.sh # Verification and troubleshooting checks
    ├── ios/
    │   ├── ios_build.sh      # Xcode archive and IPA generation
    │   ├── ios_upload.sh     # App Store / TestFlight upload automation
    │   ├── ios_utils.sh      # Certificate and provisioning profile discovery
    │   └── ios_diagnostics.sh # iOS build environment validation
    └── chat/
        ├── chat_notify.sh    # Webhook notification engine
        ├── chat_android_utils.sh # Android artifact notification formatting
        ├── chat_ios_utils.sh # iOS artifact notification formatting
        └── chat_helpers.sh   # Notification message templates
```

---

## Multi-Stack App Autodiscovery

The backend inspects the configured `WORKSPACE_ROOT` to discover projects automatically. It checks the following locations in order:

1. **Monorepo Subdirectories:**
   - `apps/*`
   - `packages/*`
   - `modules/*`
   - Sibling subdirectories directly inside the workspace.

2. **Project Type Detection:**
   - **Flutter:** Detected if `pubspec.yaml` exists. Reads app title and version from the file.
   - **Node.js / React Native:** Detected if `package.json` exists. Reads version and name.
   - **Android Native:** Detected if `build.gradle` or `settings.gradle` exists.
   - **iOS Native:** Detected if `*.xcworkspace` or `*.xcodeproj` exists.
   - **Generic / Script:** If a directory contains custom build scripts or is the root directory.

If `WORKSPACE_ROOT` points to a single project rather than a monorepo, the console treats the root folder as the target app.

---

## Execution & Job Lifecycle

Every build or deployment action undergoes a managed lifecycle:

```
[User triggers action]
         │
         ▼
[POST /api/deployment/execute]
         │
         ├─► [Concurrency Guard] ──(Is app busy?)──► Reject: APP_BUSY (409)
         │
         ├─► [Production Gate] ───(Prod target?)──► Prompt for confirmation
         │
         ▼
[Generate command & spawn subprocess]
         │
         ├─► Background thread tracks PID and exit code
         ├─► Logs write to temp directory and memory buffer
         ├─► Output streams to browser via GET /api/deployment/poll
         │
         ▼
[Job Completes]
         │
         ├─► Append summary record to deployment_history.jsonl
         ├─► Trigger optional chat webhook notification
         └─► Release app concurrency lock
```

---

## Safety & Approval Gates

### 1. Concurrency Guard
Building an application writes to intermediate directories (such as `build/`, `node_modules/`, or `.gradle/`). To prevent file corruption:
- Each application has an in-memory lock.
- If a job is running for `my_app`, subsequent requests for `my_app` receive an `APP_BUSY` status code.
- Different applications can build in parallel without conflict.

### 2. Production Approval Gate
Accidental deployments to production app stores are prevented by requiring an explicit user confirmation:
- Any action with flavor `prod` targeting store distribution (`upload_ipa`, `upload_aab`, `deploy_both`) requires `confirmed: true` in the execution payload.
- If called without confirmation, the backend returns `requires_confirmation: true`. The frontend then displays a modal detailing the app, environment, and target track.

### 3. In-Memory Secrets
Build credentials (API keys, certificates, service account tokens) are never written to disk during the build:
- macOS Keychain items are retrieved in-memory and passed as flags directly to the build tool.
- Environment variables set in `.env` are injected into the subprocess environment only.

---

## Script & Build Automation Layer

### `run_build.sh`
The primary dispatcher for all build actions. It sets up the execution environment, locates configuration files, and delegates to the appropriate platform script:

```bash
# Example syntax:
bash features/deployment/scripts/run_build.sh <action> <app_name> <env_name> [options]
```

Supported actions include:
- `buildIPA`, `uploadIPA`, `deployIPA`
- `buildAAB`, `uploadAAB`, `deployAAB`
- `buildAPK`
- `deployBothPlatforms`
- `cleanProject`
- `pubGet`

---

## Chat & Notification Integration

The console can post interactive notification cards to Google Chat or any standard webhook when builds start, succeed, or fail.

### Configuration
Set the following variable in `.env` or system environment:
```ini
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/.../messages?key=...
```

### Card Contents
- **Header:** Status badge (SUCCESS / FAILED), app title, environment name (`dev`, `qa`, `prod`).
- **Git Details:** Active branch, latest commit hash, and author.
- **Artifact Links:** Internal test track links or download locations.
- **Duration:** Total elapsed execution time.

---

## Deployment History

Every completed job is recorded to `deployment_history.jsonl`:
- **Format:** One JSON object per line.
- **Fields:** `job_id`, `app_name`, `action`, `flavor`, `status`, `start_time`, `end_time`, `duration_seconds`, `exit_code`.
- **Rotation:** Automatically managed to prevent unbounded file growth.
- **UI Access:** Viewable under the **History** tab in the deployment console.

---

## REST API Reference

The server exposes a clean REST API:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/deployment/apps` | Lists all discovered applications in the workspace |
| `GET` | `/api/deployment/templates` | Returns available action templates (e.g. Build AAB, Upload IPA) |
| `GET` | `/api/deployment/profiles` | Returns defined build profiles from `build_profiles.json` |
| `POST` | `/api/deployment/profile/save` | Saves or updates a build profile |
| `POST` | `/api/deployment/profile/delete` | Deletes a build profile |
| `POST` | `/api/deployment/command` | Previews the exact shell command that would be run |
| `POST` | `/api/deployment/execute` | Starts a build or deployment job |
| `GET` | `/api/deployment/poll` | Polls current job status and streams log output |
| `POST` | `/api/deployment/abort` | Aborts a currently running job |
| `GET` | `/api/deployment/history` | Retrieves execution history records |
| `GET` | `/api/deployment/batch/plan` | Generates a sequential batch plan for all apps |
| `POST` | `/api/deployment/batch/execute` | Executes a batch deployment plan |
| `GET` | `/api/deployment/workspaces` | Lists configured workspaces |
| `POST` | `/api/deployment/workspace/select` | Switches the active workspace dynamically |
| `POST` | `/api/deployment/webhook` | Webhook endpoint for triggering builds from CI/CD |

---

## Configuration Files

### `build_profiles.json`
Defines profiles mapping an app name to environments and configurations:
```json
{
  "APP_DEV": {
    "app_name": "my_app",
    "env_name": "dev",
    "secret_file": "dev.json"
  },
  "APP_PROD": {
    "app_name": "my_app",
    "env_name": "prod",
    "secret_file": "prod.json"
  }
}
```

### `.env`
Environment file for user-specific overrides:
```ini
WORKSPACE_ROOT=/path/to/my/workspace
DEPLOYMENT_PORT=18112
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/...
```
