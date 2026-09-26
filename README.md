# Dev Deployment Console 🚀

A lightweight, self-hosted web dashboard to build, sign, and deploy mobile and web apps — without touching the terminal.

Open `http://localhost:18112` in your browser, pick your app, choose an environment (`dev`, `qa`, `prod`), click a button, and watch your build logs scroll in real-time.

> **Location of deployment subsystem:** `features/deployment/`
> **Backend:** `features/deployment/backend/router.py` & `features/deployment/backend/server.py`
> **Frontend:** `features/deployment/frontend/{index.html, app.js, setup.js, styles.css}`
> **Default port:** `18112` (configurable via `DEPLOYMENT_PORT`)

---

## 📑 Table of Contents

1. [What Is This?](#-what-is-this)
2. [Key Features](#-key-features)
3. [Quick Start](#-quick-start)
4. [Controlling the Server](#️-controlling-the-server)
5. [How It Finds Your Apps](#-how-it-finds-your-apps)
6. [Understanding the Web Interface](#-understanding-the-web-interface)
7. [Configuring App Settings via the UI](#️-configuring-app-settings-via-the-ui)
8. [iOS App Store Connect API Key (.p8) Management](#-ios-app-store-connect-api-key-p8-management)
9. [Customizing Commands](#️-customizing-commands)
10. [Usage Examples](#-usage-examples)
11. [CI/CD Webhook Integration](#-cicd-webhook-integration)
12. [System Architecture](#-system-architecture)
13. [Directory Structure](#-directory-structure)
14. [Execution & Job Lifecycle](#-execution--job-lifecycle)
15. [Safety & Approval Gates](#-safety--approval-gates)
16. [Script & Build Automation Layer](#-script--build-automation-layer)
17. [Chat & Notification Integration](#-chat--notification-integration)
18. [Deployment History](#-deployment-history)
19. [REST API Reference](#-rest-api-reference)
20. [Configuration Files Reference](#-configuration-files-reference)
21. [Project Structure Overview](#-project-structure-overview)
22. [Contributing & Roadmap](#-contributing--roadmap)
23. [FAQ](#-frequently-asked-questions)
24. [License](#-license)

---

## 💡 What Is This?

When building apps, you constantly run commands like:
- *"Build iOS app for TestFlight"*
- *"Upload Android App Bundle to Google Play Store"*
- *"Run tests and clean the project"*
- *"Tag a new release"*

**Dev Deployment Console** replaces those terminal sessions with a clean web page on your own machine that:
1. Shows all your apps as visual cards — single projects or entire monorepos.
2. Lets you click action buttons (like **Build IPA** or **Upload AAB**).
3. Streams real terminal output live to your screen.
4. Keeps persistent history of every build (success, failure, timestamps, logs).
5. Protects you with safety gates (confirmation popup before any Production deploy).

It is **zero-intrusion** — it lives completely separately from your apps. No rewriting your codebase, no foreign dependencies installed into your projects.

---

## ✨ Key Features

- **Standardized UI System** — Frontend strictly uses the [`developer-dashboard-ui`](https://github.com/sunilbvb/developer-dashboard-ui) design system via jsDelivr CDN (`.ui-card`, `.ui-field`, `.ui-button`, `.ui-dropzone`, `.ui-badge`). No custom or fragmented CSS.
- **No Heavy Dependencies** — Built using Python's standard library. No databases, Redis, or heavy frameworks needed.
- **Universal & Stack-Agnostic** — Works with Flutter, React Native, iOS Native, Android Native, Node.js, or any custom Bash script.
- **Real-Time Live Logs** — Stdout and stderr stream live into the embedded browser terminal.
- **Secure iOS Key Management** — Upload App Store Connect API keys (`.p8`) via drag-and-drop. Keys are Base64-encoded, stored per-app, and written to Apple's industry-standard path (`~/.appstoreconnect/private_keys/`) with `chmod 600`. No key files committed to source control.
- **Accidental Deploy Protection** — Confirmation modal required before any Production store release.
- **Concurrency Guard** — Rejects duplicate jobs on the same app (`APP_BUSY`).
- **Deployment History** — Persistent audit trail with error excerpts and exit codes.
- **Multi-Workspace Support** — Switch between project workspaces dynamically from the dashboard without restarting the server.
- **Remote CI/CD Webhooks** — Trigger builds from GitHub Actions, GitLab CI, or Slack bots via HTTP POST.
- **Chat Notifications** — Sends formatted build summary cards to Google Chat or any compatible webhook.
- **Cross-Platform** — Works seamlessly on both **Linux** and **macOS**.

---

## 🏁 Quick Start

### Prerequisites
- **Python 3.11+** (`python3 --version`)
- **Bash 4+** (`bash --version`)
- Your normal build tools (Flutter, Node, Xcode, Android Studio — depending on what you build)

### Step 1 — Create your settings file

```bash
cp .env.example .env
```

Open `.env` and set your workspace path:

```ini
# Path to the project or monorepo you want to deploy
WORKSPACE_ROOT=/path/to/your/project

# Port to access the dashboard (default: 18112)
DEPLOYMENT_PORT=18112
```

> **Tip:** Leave `WORKSPACE_ROOT` blank to target the current directory automatically.

### Step 2 — Start the server

```bash
./start.sh
```

### Step 3 — Open in your browser

```
http://localhost:18112
```

Your apps will appear on the left sidebar, ready to build and deploy.

---

## 🛠️ Controlling the Server

Run the server directly with Python:

```bash
python3 features/deployment/backend/server.py --port 18112
```

Or use the background service scripts:

| Action | Command |
|:---|:---|
| **Start in background** | `./features/deployment/bin/start-deployment.sh` |
| **Stop background server** | `./features/deployment/bin/stop-deployment.sh` |
| **Check server status** | `./features/deployment/bin/status-deployment.sh` |
| **Restart** | `./features/deployment/bin/restart-deployment.sh` |

---

## 📱 How It Finds Your Apps

The console auto-discovers apps in your `WORKSPACE_ROOT`:

1. **Monorepos** — Scans `apps/`, `packages/`, `modules/`, and sibling subdirectories for project manifests.
2. **Single Projects** — If `WORKSPACE_ROOT` points directly to one app, that becomes the single app tile.
3. **Manual Registration** — Register apps via the **Configure** modal (⚙️) or by editing `.dev-dashboard/apps_config.json` directly.

**Project type detection:**

| Manifest file | Detected as |
|---|---|
| `pubspec.yaml` | Flutter |
| `package.json` | Node.js / React Native |
| `build.gradle` / `settings.gradle` | Android Native |
| `*.xcworkspace` / `*.xcodeproj` | iOS Native |
| Custom scripts / no manifest | Generic / Script |

---

## 🖥️ Understanding the Web Interface

```
┌─────────────────┬────────────────────────────────────────────────────────┐
│  SELECT APP     │  COMMANDS & TERMINAL                                   │
├─────────────────┼────────────────────────────────────────────────────────┤
│                 │  Target Environment: [ Dev ] [ QA ] [ Prod ]           │
│  📱 My Mobile   │                                                        │
│  🌐 Web Portal  │  [ 🚀 Build IPA ]   [ 📦 Build AAB ]   [ 🧹 Clean ]   │
│  ⚙️ Backend API │                                                        │
│                 ├────────────────────────────────────────────────────────┤
│                 │  Live Terminal Output:                                 │
│                 │  > Executing command...                                │
│                 │  > Running build task [SUCCESS]                        │
│                 │                                                        │
│                 │  [ Stop Job ]   [ Clear Output ]   [ History Tab ]    │
└─────────────────┴────────────────────────────────────────────────────────┘
```

| Area | What it does |
|---|---|
| **Left Panel (App Grid)** | All detected apps. Click to select one. |
| **Environment Tabs** | Switch flavors: `dev`, `qa`, `prod`, etc. |
| **Command Cards** | Clickable action buttons: Build, Upload, Clean, Release. |
| **Live Terminal** | Real-time log streaming as the build runs. |
| **History Tab** | Past builds — status, timestamps, error excerpts, full logs. |
| **Configure (⚙️)** | Setup modal for credentials, bundle IDs, and app settings. |
| **Switch / Add Project** | Switch between workspaces without restarting the server. |

---

## ⚙️ Configuring App Settings via the UI

1. Click **Configure** (⚙️) in the top-right header.
2. Select your app from the left sidebar of the modal.
3. Fill in the details for each section:

   **App Identifiers** — iOS Bundle IDs and Android Package Names per flavor (`dev`, `qa`, `prod`).

   **iOS Credentials** — Apple ID email, App Store Connect Issuer ID, and API Key (.p8) upload.

   **Android Credentials** — Google Play Service Account JSON path.

   **Auto-Release** — Optionally auto-trigger a release action after a successful deploy.

4. Click **Save Config**.

> You can also manually edit `.dev-dashboard/deploy_config.json` if you prefer JSON.

---

## 🔑 iOS App Store Connect API Key (.p8) Management

### Why this matters

Having `.p8` key files stored in the project's `private_keys/` folder is a security risk — they can accidentally be committed to source control. This tool follows **Apple's industry-standard** approach instead.

### How to upload a key (Web UI)

1. Open **Configure** (⚙️) → select your app.
2. Enter your **App Store Connect Issuer ID** (UUID from App Store Connect → Users & Access → Integrations → Team ID).
3. Drag and drop your `AuthKey_XXXXXXXXXX.p8` file onto the **API Key dropzone** — or click to browse.
4. The console automatically:
   - Extracts the **Key ID** from the filename (`AuthKey_<KeyID>.p8`).
   - **Base64-encodes** the file content.
   - Saves `apple_key_id`, `apple_p8_base64`, and `apple_issuer_id` into `.dev-dashboard/deploy_config.json`.
   - Writes the raw `.p8` file to `~/.appstoreconnect/private_keys/AuthKey_<KeyID>.p8` with `chmod 600`.

> **Filename convention:** The file **must** follow `AuthKey_XXXXXXXXXX.p8` (10-character uppercase Key ID). This is the exact filename Apple uses when you download from App Store Connect — no renaming needed.

### Key path resolution priority (in bash scripts)

All iOS scripts (`ios_utils.sh`, `ios_build.sh`, `ios_upload.sh`, `Fastfile`) resolve the p8 key using this priority order:

| Priority | Source | Notes |
|---|---|---|
| **1 (highest)** | `APPLE_API_KEY_BASE64` env var | In-memory Base64; decoded to standard path at runtime |
| **2** | `~/.appstoreconnect/private_keys/AuthKey_<KeyID>.p8` | Apple's own recommended standard location |
| **3** | `~/.private_keys/AuthKey_<KeyID>.p8` | Apple secondary fallback |
| **4 (lowest)** | `<workspace>/private_keys/AuthKey_<KeyID>.p8` | Legacy path — supported for backward compat |

### Multiple apps — multiple keys

Each app stores its own key independently:

```json
{
  "apps": {
    "customer_app": { "apple_key_id": "ABCD123456", ... },
    "driver_app":   { "apple_key_id": "WXYZ789012", ... }
  }
}
```

### Upload via API (programmatic)

**Option A — multipart/form-data:**
```bash
curl -X POST http://localhost:18112/api/deployment/p8/upload \
  -F "app_id=my_app" \
  -F "issuer_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  -F "file=@/path/to/AuthKey_ABCD123456.p8;filename=AuthKey_ABCD123456.p8"
```

**Option B — JSON with Base64:**
```bash
curl -X POST http://localhost:18112/api/deployment/p8/upload \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "my_app",
    "filename": "AuthKey_ABCD123456.p8",
    "issuer_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "content_base64": "<base64-encoded-p8-content>"
  }'
```

**Response:**
```json
{
  "success": true,
  "key_id": "ABCD123456",
  "stored_path": "/home/user/.appstoreconnect/private_keys/AuthKey_ABCD123456.p8",
  "b64_stored": true,
  "app_id": "my_app"
}
```

---

## ⚙️ Customizing Commands

Commands are defined in [`config/deployment_templates.json`](config/deployment_templates.json). Add, change, or remove commands freely.

### Example: Add a custom shell command

```json
{
  "id": "build_web",
  "name": "Build Web App",
  "description": "Compile production web bundle",
  "runner": "direct",
  "command_template": "npm run build -- --mode {flavor}",
  "icon": "globe",
  "color": "#3b82f6"
}
```

### Supported template placeholders

| Placeholder | Replaced with |
|---|---|
| `{flavor}` | Selected environment (`dev`, `qa`, `prod`, …) |
| `{app_id}` | The app's folder name or identifier |
| `{bundle_id}` | iOS Bundle ID or Android package name for the selected flavor |

---

## 📖 Usage Examples

### Example 1 — Build a Flutter Android App Bundle

1. Set `WORKSPACE_ROOT=/home/user/my-flutter-app` in `.env`.
2. Run `./start.sh` and open `http://localhost:18112`.
3. Click your app → click **Prod** tab → click **Build AAB**.
4. A safety confirmation popup appears for Production — click **Confirm & Deploy**.
5. Watch Gradle and Flutter output stream live. A green banner appears on success with the `.aab` file path.

---

### Example 2 — Deploy a React / Next.js Web App

Add a custom template to `config/deployment_templates.json`:

```json
{
  "utility": [{
    "id": "build_web_prod",
    "name": "Build Web Production",
    "runner": "direct",
    "command_template": "npm run build",
    "icon": "globe",
    "color": "#3b82f6"
  }]
}
```

Set `WORKSPACE_ROOT=/home/user/my-web-project`, start the server, and click **Build Web Production**.

---

### Example 3 — Deploy All Apps at Once (Batch Mode)

For a monorepo with `apps/customer_app`, `apps/driver_app`, `apps/admin_portal`:

1. Click **Deploy All Apps** in the top-right header.
2. Choose **Target Environment** and **Action** (e.g. `Build AAB`).
3. Click **Start Batch** — apps are built sequentially with live progress per app.

---

### Example 4 — Stop a Running Build

Click the red **Stop Job** button in the terminal toolbar. The server sends `SIGTERM`/`SIGKILL` to the process group and frees the app lock.

---

### Example 5 — Check Build History

Click the **History** tab above the terminal. The table shows:
- App Name, Command, Status (✅ / ❌ / 🛑), Started Time, Duration.
- Click any row to expand the full console log.

---

## 🌐 CI/CD Webhook Integration

Trigger builds remotely from GitHub Actions, GitLab CI, or any script:

```bash
curl -X POST http://localhost:18112/api/deployment/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "app": "my-app",
    "templateId": "build_aab",
    "flavor": "prod"
  }'
```

**Response:**
```json
{ "success": true, "jobId": "job_1783281928_a1b2", "status": "running" }
```

### Sample GitHub Actions workflow

```yaml
name: Trigger Local Deployment
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Build via Webhook
        run: |
          curl -X POST http://your-server-ip:18112/api/deployment/webhook \
            -H "Content-Type: application/json" \
            -d '{"app":"my-flutter-app","templateId":"build_aab","flavor":"prod"}'
```

---

## 🏗️ System Architecture

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
│       Routing · CORS · Static files · Multipart uploads     │
│                           :18112                            │
└──────────────────────────────┬──────────────────────────────┘
                               │ Direct function calls
┌──────────────────────────────▼──────────────────────────────┐
│                    Router & Process Engine                  │
│             features/deployment/backend/router.py           │
│  App autodiscovery · Command generator · Subprocess runner  │
│  Job state management · Concurrency locking                 │
│  p8 key upload & storage · Workspace switching              │
│  Log buffer & history writer                                │
└──────────────────────────────┬──────────────────────────────┘
                               │ Subprocess execution
┌──────────────────────────────▼──────────────────────────────┐
│                     Bash Script Engine                      │
│             features/deployment/scripts/                    │
│  run_build.sh (entry)      json_utils.sh (helpers)          │
│  android/ (build & upload) ios/ (build & upload)            │
│  chat/ (notifications)     build_secrets.sh (keychain)      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Directory Structure

```
dev-deployment/
├── config/
│   ├── deployment_templates.json    # Define available build & deploy buttons
│   ├── workspaces_list.json         # Multi-workspace list (auto-managed)
│   ├── workspaces_list.example.json # Example multi-workspace config
│   └── active_workspace.example.txt # Example workspace pointer
├── features/
│   └── deployment/
│       ├── backend/
│       │   ├── server.py            # HTTP server: routing, CORS, static, multipart upload
│       │   └── router.py            # Core engine: discovery, execution, p8 upload, history
│       ├── bin/
│       │   ├── start-deployment.sh  # Background launcher
│       │   ├── stop-deployment.sh   # Graceful stop
│       │   ├── restart-deployment.sh
│       │   └── status-deployment.sh
│       ├── docs/                    # (legacy — now consolidated here)
│       ├── fastlane/
│       │   ├── Fastfile             # iOS TestFlight lane (p8 Base64 aware)
│       │   └── Gemfile              # Self-contained Fastlane dependency definition
│       ├── frontend/
│       │   ├── index.html           # Main dashboard UI
│       │   ├── app.js               # App selection, execution, polling, log streaming
│       │   ├── setup.js             # Setup modal: credentials, p8 dropzone, workspace
│       │   └── styles.css           # Theme styles
│       └── scripts/
│           ├── run_build.sh         # Primary bash command dispatcher
│           ├── json_utils.sh        # Helper functions: profile parsing, env loading
│           ├── build_secrets.sh     # In-memory secret loading from Keychain
│           ├── setup_keychain.sh    # Interactive Keychain setup helper
│           ├── android/
│           │   ├── android_utils.sh # AAB/APK build & Google Play upload
│           │   └── android_diagnostics.sh
│           ├── ios/
│           │   ├── ios_build.sh     # Xcode archive & IPA generation
│           │   ├── ios_upload.sh    # App Store / TestFlight upload
│           │   ├── ios_utils.sh     # Cert & provisioning profile discovery
│           │   └── ios_diagnostics.sh
│           └── chat/
│               ├── chat_notify.sh
│               ├── chat_android_utils.sh
│               ├── chat_ios_utils.sh
│               └── chat_helpers.sh
├── frontend/                        # Shared UI assets and component library
├── start.sh                         # Main startup script (run this!)
├── .env.example                     # Environment variable template
└── .gitignore                       # Excludes secrets, keys, pid files, logs
```

---

## 🔄 Execution & Job Lifecycle

Every build or deployment action goes through a managed lifecycle:

```
[User clicks action button]
         │
         ▼
[POST /api/deployment/execute]
         │
         ├─► [Concurrency Guard] ──(app busy?)──► Reject: APP_BUSY (409)
         │
         ├─► [Production Gate] ───(prod flavor?)─► Show confirmation modal
         │
         ▼
[Generate command & spawn subprocess]
         │
         ├─► Background thread tracks PID and exit code
         ├─► Logs written to temp dir and in-memory buffer
         ├─► Output streamed to browser via GET /api/deployment/job
         │
         ▼
[Job Completes]
         │
         ├─► Append summary record to deployment_history.jsonl
         ├─► Trigger optional chat webhook notification
         └─► Release app concurrency lock
```

---

## 🛡️ Safety & Approval Gates

### 1. Concurrency Guard
- Each app has an in-memory execution lock.
- A second build request for a busy app returns `APP_BUSY (409)`.
- Different apps can build in parallel without conflict.

### 2. Production Approval Gate
- Any action with flavor `prod` targeting store distribution requires `confirmed: true` in the payload.
- Without it, the backend returns `requires_confirmation: true` and the frontend shows a detailed confirmation modal (app name, environment, target track).

### 3. In-Memory Secrets
- macOS Keychain items are retrieved and passed as flags directly to the build tool — never written to disk during the build.
- Environment variables from `.env` are injected into the subprocess environment only.

---

## 🔧 Script & Build Automation Layer

### `run_build.sh` — Primary dispatcher

```bash
bash features/deployment/scripts/run_build.sh <action> <app_name> <env_name> [options]
```

| Action | Description |
|---|---|
| `buildIPA` | Xcode archive + IPA export |
| `uploadIPA` | Upload IPA to TestFlight |
| `deployIPA` | Build + Upload IPA |
| `buildAAB` | Gradle AAB build |
| `uploadAAB` | Upload AAB to Google Play |
| `deployAAB` | Build + Upload AAB |
| `buildAPK` | Gradle APK build |
| `deployBothPlatforms` | Build + upload iOS and Android together |
| `cleanProject` | Flutter / Gradle clean |
| `pubGet` | `flutter pub get` |

---

## 💬 Chat & Notification Integration

Post interactive build summary cards to Google Chat or any standard webhook.

### Setup

```ini
# In .env
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/.../messages?key=...
```

### Card Contents

- **Status badge** — SUCCESS / FAILED
- **App title & environment** — `my_app (prod)`
- **Git details** — branch, commit hash, author
- **Artifact links** — TestFlight / Play Store track links
- **Duration** — total elapsed build time

---

## 📋 Deployment History

Every completed job is recorded to `<WORKSPACE_ROOT>/.dev-dashboard/deployment_history.jsonl`:

- **Format:** One JSON object per line (append-only)
- **Fields:** `job_id`, `app_name`, `action`, `flavor`, `status`, `start_time`, `end_time`, `duration_seconds`, `exit_code`
- **Rotation:** Auto-managed to prevent unbounded growth
- **UI:** Viewable under the **History** tab in the console

---

## 🌐 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/deployment/apps` | Lists all discovered apps in the workspace |
| `GET` | `/api/deployment/commands` | Returns generated command cards (`?app=<id>`) |
| `GET` | `/api/deployment/templates` | Returns available action templates |
| `GET` | `/api/deployment/deploy-config` | Returns full per-app deployment configuration |
| `POST` | `/api/deployment/deploy-config/save` | Saves per-app deployment configuration |
| `POST` | `/api/deployment/apps` | Registers a new app in `apps_config.json` |
| `POST` | `/api/deployment/p8/upload` | Uploads an App Store Connect API key (`.p8`); supports `multipart/form-data` or JSON+Base64 |
| `POST` | `/api/deployment/execute` | Starts a build or deployment job |
| `GET` | `/api/deployment/job` | Polls job status and streams log output (`?id=<jobId>`) |
| `POST` | `/api/deployment/job/stop` | Stops a running job |
| `GET` | `/api/deployment/history` | Retrieves history (`?app=`, `?flavor=`, `?status=`, `?limit=`) |
| `GET` | `/api/deployment/batch-plan` | Generates a batch plan (`?flavor=`, `?templateId=`) |
| `GET` | `/api/deployment/workspaces` | Lists configured workspaces |
| `POST` | `/api/deployment/workspace/select` | Switches the active workspace dynamically |
| `POST` | `/api/deployment/inject-melos` | Injects deployment commands into `pubspec.yaml` |
| `POST` | `/api/deployment/regenerate-commands` | Rebuilds cached command cards for all apps |
| `GET` | `/api/deployment/scan-config` | Auto-scans and returns detected config (`?app=`) |
| `POST` | `/api/deployment/scan-all` | Bulk scans all apps in workspace and merges discovered Bundle IDs & package names |
| `GET` | `/api/deployment/inspect-path` | Inspects candidate directory path before opening (`?path=`) — returns app counts, tech stacks, monorepo state |
| `GET` | `/api/deployment/ios-cert-check` | Checks iOS cert/profile expiry (`?app=`, `?flavor=`) |
| `POST` | `/api/deployment/webhook` | Triggers a build from CI/CD |

---

## 📁 Configuration Files Reference

### `.dev-dashboard/apps_config.json`
Auto-managed list of registered apps:
```json
[
  { "id": "my_app", "name": "My App", "color": "#8b5cf6", "icon": "smartphone", "version": "1.0.0 (1)" }
]
```

### `.dev-dashboard/deploy_config.json`
Per-app credentials and settings (managed via Setup modal or API):
```json
{
  "apps": {
    "<app_id>": {
      "flavors": ["dev", "qa", "prod"],
      "apple_id": "developer@company.com",
      "apple_issuer_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "apple_key_id": "ABCD123456",
      "apple_p8_base64": "LS0tLS1CRUdJTi...",
      "play_service_account_path": "private_keys/play-service-account.json",
      "bundle_id_dev": "com.company.app.dev",
      "bundle_id_qa": "com.company.app.qa",
      "bundle_id_prod": "com.company.app",
      "android_package_dev": "com.company.app.dev",
      "android_package_prod": "com.company.app",
      "auto_release_on_success": false,
      "auto_release_action": "release_push",
      "auto_release_flavors": ["prod"]
    }
  }
}
```

### `config/deployment_templates.json`
Defines the action buttons available in the dashboard. Groups: `ios`, `android`, `utility`, `release`.

### `.env`
User-specific environment overrides (never committed):
```ini
WORKSPACE_ROOT=/path/to/my/workspace
DEPLOYMENT_PORT=18112
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/...
```

### `config/workspaces_list.json`
Auto-managed list of known workspaces (written when you switch workspaces from the UI):
```json
["/home/user/project-a", "/home/user/project-b"]
```

---

## 📂 Project Structure Overview

```text
dev-deployment/
├── config/
│   ├── deployment_templates.json    # Build & deploy action definitions
│   ├── workspaces_list.json         # Auto-managed workspace list
│   └── active_workspace.example.txt # Workspace pointer example
├── features/
│   └── deployment/                  # Full deployment subsystem
│       ├── backend/                 # Python HTTP server & router
│       ├── bin/                     # Start/stop/restart scripts
│       ├── fastlane/                # iOS Fastlane lanes
│       ├── frontend/                # Web dashboard (HTML, JS, CSS)
│       └── scripts/                 # Bash build & upload automation
├── frontend/                        # Shared UI component library
├── start.sh                         # Main entry point
├── .env.example                     # Environment template
└── .gitignore                       # Excludes keys, secrets, logs, pid files
```

---

## 🤝 Contributing & Roadmap

We love open-source contributions! Want to help make Dev Deployment Console better?

Check out our **[CONTRIBUTING.md](CONTRIBUTING.md)** for:
- 🚀 **Feature Wishlist & Ideas** (Melos monorepo scanning improvements, bulk workspace auto-scan, Slack/Discord webhooks, etc.)
- 🛠️ **Dev Setup & PR Guidelines**
- 🎨 **Code Standards**

---

## ❓ Frequently Asked Questions

### How do I change the port?
Set `DEPLOYMENT_PORT` in `.env`, or pass it directly:
```bash
DEPLOYMENT_PORT=8080 ./start.sh
```

### My app list shows nothing — what's wrong?
Check `WORKSPACE_ROOT` in `.env`. It must point to a valid directory with your app or monorepo. If still empty, use the **Configure** modal to register apps manually.

### Can I run this on Linux?
**Yes.** The server and all script executors are fully compatible with both Linux and macOS. Paths and shell runners adapt automatically.

### Are my secrets safe?
**Yes.** `.env` files, `.pid` files, build logs, private keystores, certificate files, and `.p8` key files are all excluded in `.gitignore`. For iOS App Store Connect API keys, the console uses Apple's industry-standard path (`~/.appstoreconnect/private_keys/`) and stores the Base64-encoded key in `.dev-dashboard/deploy_config.json` — both excluded from version control. Keys are written with `chmod 600` (owner read/write only).

### Can I commit `.dev-dashboard/` to Git?
**Yes — optionally.** Committing it lets your whole team share the same app configuration, Bundle IDs, and command setup. Just make sure `apple_p8_base64` and any service account paths are excluded (add them to `.gitignore`) if you don't want key material in your repo.

### What Python version is required?
Python **3.11 or higher**. The server uses `email.parser.BytesFeedParser` for multipart uploads (replaces the removed `cgi` module from Python 3.13+).

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
