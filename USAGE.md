# How to Use Dev Deployment Console (Complete Guide with Examples) 📘

This guide walks you through using Dev Deployment Console step-by-step with real-world examples.

---

## 📑 Table of Contents
1. [How This Console Connects to Your Apps (Integration Overview)](#1-how-this-console-connects-to-your-apps-integration-overview)
2. [Understanding the Web Interface](#2-understanding-the-web-interface)
3. [Example 1: Building a Flutter Mobile App](#example-1-building-a-flutter-mobile-app)
4. [Example 2: Deploying a React Native or Web App](#example-2-deploying-a-react-native-or-web-app)
5. [Example 3: Deploying All Apps at Once (Batch Mode)](#example-3-deploying-all-apps-at-once-batch-mode)
6. [Example 4: Triggering from CI/CD (GitHub Actions)](#example-4-triggering-from-cicd-github-actions)
7. [Stopping a Running Build](#stopping-a-running-build)
8. [Checking Build History & Logs](#checking-build-history--logs)

---

## 1. How This Console Connects to Your Apps (Integration Overview)

### A. Zero Code Intrusion
The deployment console lives completely separate from your applications. It does **not** force you to rewrite your codebase or install foreign dependencies.

### B. Pointing to Your Apps
You connect your app simply by pointing the `WORKSPACE_ROOT` variable in `.env`:

* **For a Single App:**
  ```ini
  WORKSPACE_ROOT=/home/user/projects/my-single-app
  ```
  The console inspects the directory, auto-detects the project type (Flutter, React Native, Node, Android, iOS), and creates an app tile on your dashboard.

* **For a Monorepo (Multiple Apps):**
  ```ini
  WORKSPACE_ROOT=/home/user/projects/my-monorepo
  ```
  If your repo has subfolders like:
  ```text
  my-monorepo/
  ├── apps/
  │   ├── customer_mobile/
  │   ├── driver_mobile/
  │   └── admin_web/
  ```
  The console automatically detects each app inside `apps/` (or `packages/`) and lists each as its own selectable card on the left panel!

### C. What Gets Created in Your App's Directory?
When connected, the console creates a lightweight, isolated config folder inside your workspace root:

```text
<your-workspace>/
└── .dev-dashboard/
    ├── apps_config.json        # App metadata (display names, colors, icons, versions)
    ├── deploy_config.json      # Per-app settings (Bundle IDs, Android package names)
    └── commands_config.json    # Cached command templates for quick execution
```

> **Git Tip:** You can add `.dev-dashboard/` to your target app's `.gitignore` if you want local-only settings, or commit it so your whole team shares the same deployment configuration!

### D. Configuring App Details via the Web UI
You do not have to edit JSON files manually:
1. In the top-right header of the console, click **Configure** (⚙️).
2. Select your app from the dropdown.
3. Fill in your Bundle IDs, Android Package names, and Apple Team IDs for each flavor (`dev`, `qa`, `prod`).
4. Click **Save Configuration** — the console will automatically update and prepare all build buttons.

---

## 2. Understanding the Web Interface

When you run `./start.sh` and open `http://localhost:18112`, here is what you see:

```text
┌─────────────────┬────────────────────────────────────────────────────────┐
│  SELECT APP     │  COMMANDS & TERMINAL                                   │
├─────────────────┼────────────────────────────────────────────────────────┤
│                 │  Target Environment: [ Dev ] [ Staging ] [ Prod ]      │
│  📱 My Mobile   │                                                        │
│  🌐 Web Portal  │  [ 🚀 Build IPA ]   [ 📦 Build AAB ]   [ 🧹 Clean ]     │
│  ⚙️ Backend API │                                                        │
│                 ├────────────────────────────────────────────────────────┤
│                 │  Live Terminal Output:                                 │
│                 │  > Executing command...                                │
│                 │  > Running build task [SUCCESS]                        │
│                 │                                                        │
│                 │  [ Stop Job ]   [ Clear Output ]   [ History Tab ]     │
└─────────────────┴────────────────────────────────────────────────────────┘
```

1. **Left Panel (App Grid):** Shows all detected apps in your workspace. Click an app to select it.
2. **Environment Tabs:** Switch between flavors like `dev`, `staging`, and `prod`.
3. **Command Cards:** Clickable buttons representing actions like Build, Clean, Upload, or Release.
4. **Live Terminal:** Real-time log box that displays build output as it happens.
5. **History Tab:** View past builds, timestamps, status (Success/Failed), and full error logs.

---

## Example 1: Building a Flutter Mobile App

### Scenario
You have a Flutter app located at `/home/user/my-flutter-app`. You want to build a release Android App Bundle (AAB) for production.

### Step 1: Point to your Flutter app
In your `.env` file:
```ini
WORKSPACE_ROOT=/home/user/my-flutter-app
DEPLOYMENT_PORT=18112
```

### Step 2: Start the console
```bash
./start.sh
```
Open `http://localhost:18112`.

### Step 3: Run the build
1. Click your app card on the left sidebar.
2. Click the **Prod** environment tab.
3. Click the **Build AAB** command card.
4. If this is a store-shipping command, a safety confirmation popup appears:
   * Click **Confirm & Deploy**.
5. Watch the live terminal stream the Gradle and Flutter build output.
6. When complete, a green success banner appears, and the finished `.aab` file path is printed in the logs!

---

## Example 2: Deploying a React Native or Web App

### Scenario
You want to deploy a React / Next.js web application by running `npm run build`.

### Step 1: Add your custom command template
Open [`config/deployment_templates.json`](config/deployment_templates.json) and add your custom action under `"utility"`:

```json
{
  "utility": [
    {
      "id": "build_web_prod",
      "name": "Build Web Production",
      "description": "Compile production web bundle with npm",
      "runner": "direct",
      "command_template": "npm run build",
      "icon": "globe",
      "color": "#3b82f6"
    }
  ]
}
```

### Step 2: Point to your project and start
In `.env`:
```ini
WORKSPACE_ROOT=/home/user/my-web-project
```
Run:
```bash
./start.sh
```

### Step 3: Trigger the command
In the browser, select your web app and click **Build Web Production**. The console executes `npm run build` directly in your project directory and streams the output!

---

## Example 3: Deploying All Apps at Once (Batch Mode)

If you have a monorepo with multiple apps (e.g. `apps/customer_app`, `apps/driver_app`, `apps/admin_portal`):

1. Look at the top right of the page and click **Deploy All Apps**.
2. A batch modal opens:
   * **Target Environment:** Choose `dev`, `staging`, or `prod`.
   * **Action:** Choose which command to run across all apps (e.g., `Build AAB` or `Clean`).
3. Click **Start Batch**.
4. The console builds each app sequentially one after another, reporting real-time progress for each app in the list.

---

## Example 4: Triggering from CI/CD (GitHub Actions)

You can trigger a build from GitHub Actions, GitLab CI, or any script automatically.

### Sample GitHub Actions Workflow (`.github/workflows/deploy.yml`):

```yaml
name: Trigger Local Deployment

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Build via Webhook
        run: |
          curl -X POST http://your-server-ip:18112/api/deployment/webhook \
            -H "Content-Type: application/json" \
            -d '{
              "app": "my-flutter-app",
              "templateId": "build_aab",
              "flavor": "prod"
            }'
```

---

## Stopping a Running Build

If you started a build by accident or want to cancel it:
1. Look at the top right of the terminal box.
2. Click the red **Stop Job** button.
3. The server sends a termination signal (`SIGTERM` / `SIGKILL`) to the process group and safely frees the app lock.

---

## Checking Build History & Logs

1. Click the **History** tab located next to the **Terminal** tab above the output box.
2. You will see a table with:
   * **App Name**
   * **Command Run**
   * **Status** (✅ Success / ❌ Failed / 🛑 Stopped)
   * **Started Time & Duration**
3. Click any row to expand and view the full console log recorded for that build.
