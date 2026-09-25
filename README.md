# Dev Deployment Console 🚀

A simple, lightweight web dashboard to run, monitor, and manage build and deployment pipelines for your apps.

Instead of running complex commands in terminal windows, you can open a clean web page in your browser, pick your app, choose an environment (like `dev`, `staging`, or `prod`), click a button, and watch your build logs scroll in real-time.

> 📘 **Looking for complete step-by-step examples?** Check out the [User Guide with Examples (USAGE.md)](USAGE.md)!

---

## 💡 What Is This? (In Simple Words)

When building apps (mobile apps, web apps, or backend services), you often have to run commands like:
* "Build iOS app for test"
* "Upload Android app bundle to Google Play Store"
* "Run tests and clean project"
* "Tag a new release"

**Dev Deployment Console** gives you a friendly web page on your own computer (`http://localhost:18112`) that:
1. Shows all your apps as visual cards.
2. Lets you click an action button (like **Build IPA** or **Upload AAB**).
3. Streams the real terminal output live to your screen.
4. Keeps a persistent history of previous builds (success, failure, timestamps).
5. Protects you with safety checks (e.g., asking for confirmation before deploying to Production).

---

## ✨ Key Features

- **No Heavy Dependencies:** Built using Python's standard library. No external databases, Redis, or heavy frameworks required to run the dashboard.
- **Universal & Stack-Agnostic:** Works with Flutter, React Native, iOS Native, Android Native, Node.js, or any custom Bash script.
- **Real-Time Live Logs:** Watch stdout and stderr scroll live in an embedded browser terminal.
- **Accidental Deploy Protection:** Built-in confirmation modal pops up before running any production release.
- **Concurrency Guard:** Rejects accidental double-clicks or duplicate jobs on the same app (`APP_BUSY`).
- **Deployment History:** Keeps an audit trail of previous runs with error excerpts and exit codes.
- **Remote CI/CD Webhooks:** Trigger builds from GitHub Actions, GitLab CI, or Slack bots using a simple HTTP POST request.
- **Cross-Platform:** Works seamlessly on both **Linux** and **macOS**.

---

## 🏁 Quick Start (Easy 3 Steps)

### Prerequisites
Make sure you have:
* **Python 3.9+** installed (`python3 --version`)
* **Bash 4+** (`bash --version`)
* Your normal build tools (like Flutter, Node, Xcode, or Android Studio depending on what you build).

---

### Step 1: Create your settings file

In the project folder, copy the example environment file:

```bash
cp .env.example .env
```

Open `.env` in any text editor and set the path to your app:

```ini
# Path to the project or monorepo you want to deploy
WORKSPACE_ROOT=/path/to/your/project

# Port to access the dashboard (default is 18112)
DEPLOYMENT_PORT=18112
```

> **Tip:** If you leave `WORKSPACE_ROOT` blank, it will automatically target the current directory!

---

### Step 2: Start the server

Run the start script:

```bash
./start.sh
```

---

### Step 3: Open in your browser

Open your browser and visit:

```text
http://localhost:18112
```

You will see your apps listed on the left, ready to run commands!

---

## 🛠️ Controlling the Background Service (Optional)

If you prefer to run the server in the background:

| Action | Command |
| :--- | :--- |
| **Start server in background** | `./features/deployment/bin/start-deployment.sh` |
| **Stop background server** | `./features/deployment/bin/stop-deployment.sh` |
| **Check server status** | `./features/deployment/bin/status-deployment.sh` |
| **Restart background server** | `./features/deployment/bin/restart-deployment.sh` |

---

## 📱 How It Finds Your Apps

The console automatically detects apps in your workspace:

1. **Monorepos:** If your workspace has an `apps/` or `packages/` directory, it scans each subfolder for project manifests (`pubspec.yaml`, `package.json`, `build.gradle`, etc.) and lists them as separate app tiles.
2. **Single Projects:** If you point `WORKSPACE_ROOT` directly to a single app folder, it detects it and shows one app tile ready for action.
3. **Custom Manual Apps:** You can manually edit or register apps via the web UI (using the **Configure** button) or in `.dev-dashboard/apps_config.json`.

---

## ⚙️ How to Customize Commands

Commands are defined in a simple JSON file located at [`config/deployment_templates.json`](config/deployment_templates.json).

You can easily add, change, or remove commands.

### Example: Running a direct shell command
To add a custom command (e.g. for Node, Gradle, or Make), add an entry with `"runner": "direct"`:

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

### Supported Template Placeholders:
* `{flavor}`: Replaced by selected environment (`dev`, `staging`, `prod`, etc.).
* `{app_id}`: Replaced by the app's folder or identifier.
* `{bundle_id}`: Replaced by the app's iOS Bundle ID or Android package name.

---

## 🌐 Triggering Builds Remotely (CI/CD Webhook)

You can trigger a build from another machine, a CI/CD pipeline (GitHub Actions, GitLab CI), or a script using an HTTP POST request:

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
{
  "success": true,
  "jobId": "job_1783281928_a1b2",
  "status": "running"
}
```

---

## 📂 Project Structure Overview

```text
dev-deployment/
├── config/
│   ├── deployment_templates.json    # Define available build & deploy buttons
│   ├── workspaces_list.example.json # Example multi-workspace configuration
│   └── active_workspace.example.txt # Example workspace pointer
├── features/
│   └── deployment/
│       ├── backend/
│       │   ├── server.py            # Main HTTP API server
│       │   └── router.py            # Process execution, job logs, and safety guards
│       ├── frontend/                # Web dashboard (HTML, CSS, JS)
│       ├── bin/                     # Scripts to start/stop server in background
│       └── scripts/                 # Reusable build helpers & fastlane wrappers
├── frontend/                        # Shared UI assets and styles
├── start.sh                         # Main startup script (Run this!)
├── .env.example                     # Environment template
└── .gitignore                       # Ensures no secrets or temp files get committed
```

---

## ❓ Frequently Asked Questions (FAQ)

### 1. How do I change the port?
Set `DEPLOYMENT_PORT` in your `.env` file, or pass it directly:
```bash
DEPLOYMENT_PORT=8080 ./start.sh
```

### 2. What if my app list shows nothing?
Check your `WORKSPACE_ROOT` in `.env`. Make sure it points to a valid directory containing your app or monorepo. If no files are detected, the console will automatically treat your root folder as a generic app.

### 3. Can I run this on Linux?
**Yes!** The server and script executors are fully compatible with both Linux and macOS. Temporary file paths and shell runners automatically adapt to your operating system.

### 4. Are my secrets safe?
**Yes.** All local `.env` files, `.pid` files, build logs, private keystores, and certificate files are excluded in [`.gitignore`](.gitignore). Never commit your `.env` file to Git.

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
