# Frequently Asked Questions (FAQ) 📖

Welcome to the Dev Deployment Console FAQ. This document is the comprehensive single source of truth for setup, configuration, discovery, deployment, security, and troubleshooting.

For high-level guides and setup walkthroughs, see the main [README.md](README.md).

---

## 📑 Table of Contents

1. [Getting Started](#1-getting-started)
2. [Project Setups](#2-project-setups)
3. [Configuration](#3-configuration)
4. [Building and Deploying](#4-building-and-deploying)
5. [Security](#5-security)
6. [Troubleshooting](#6-troubleshooting)
7. [Known Limitations](#7-known-limitations)

---

## 1. Getting Started

### What is this tool, and who is it for?
Dev Deployment Console is a lightweight, local web dashboard designed for mobile and web developers. It provides a point-and-click UI to build, sign, and upload apps (Flutter, React Native, iOS/Android Native, Node) to TestFlight and Google Play Store without manually typing terminal commands or memorizing CLI flags.

### What do I need installed?
- **Python ≥ 3.10** (standard library only; no pip dependencies required).
- **Bash 4+** (standard on Linux; installed via Homebrew on macOS).
- Your ecosystem build tools (Flutter SDK, Xcode & CocoaPods on macOS, Android Studio / JDK, fastlane, or bundletool/ipatool depending on your stack).
See [README Prerequisites](README.md#-prerequisites).

### How do I start and stop it? Where do I find the auth token?
Run `./start.sh` or `python3 features/deployment/backend/server.py --port 18112`. To run in the background, use `./features/deployment/bin/start-deployment.sh` and stop with `stop-deployment.sh`.
The API token is auto-generated on first run and saved to `~/.config/dev-deployment/auth_token.txt`. The web UI injects this token automatically on localhost; for custom API requests, pass the `X-API-Token` header.
See [Controlling the Server](README.md#️-controlling-the-server).

---

## 2. Project Setups

### How do I add a single Flutter app with no flavors?
Set `WORKSPACE_ROOT=/path/to/your/app` in `.env` (or switch to it via the dashboard). The discovery engine identifies `pubspec.yaml`, detects no `productFlavors` or xcconfig flavor schemes, and generates clean commands without `--flavor` flags (e.g. `flutter build appbundle --release`).
See [How It Finds Your Apps](README.md#-how-it-finds-your-apps).

### How do I add a folder that contains several projects?
Point `WORKSPACE_ROOT` to the parent folder. The discovery engine traverses up to 3 levels deep across `apps/`, `packages/`, `modules/`, and sibling directories. Each project with a manifest (`pubspec.yaml`, `package.json`, `build.gradle`, `.xcodeproj`) appears as its own selectable app card.

### How does it work with a Melos workspace (apps plus packages)?
The engine reads `melos.yaml` (or `melos:` in `pubspec.yaml`), expands directory globs such as `apps/**` and `packages/*`, and applies `ignore:` patterns (such as `**/example/**`). Apps with runnable entrypoints become deployable tiles, while pure libraries are marked as packages without build buttons.

### Does it support Melos 7 / Dart pub workspaces?
Yes. The engine parses the Dart 3.5+ / Melos 7 `workspace:` manifest list inside root `pubspec.yaml`. Declared packages and applications are indexed automatically without requiring a legacy `melos.yaml`.

### How do I switch between workspaces? Why is my folder refused?
Click **Switch / Add Project** in the header or use the dropdown. For security against path traversal, the server only switches to folders listed in `config/workspaces_list.json` or under authorized directories. If a folder is unlisted, the UI prompts: *"Allow this folder?"* and automatically adds it via the `/api/deployment/workspace/allow` endpoint.

---

## 3. Configuration

### How does it read the bundle ID, package name and flavors?
- **Android**: Parses `applicationId` and `namespace` from `build.gradle` / `build.gradle.kts`, using whole-segment regex matching to avoid substring collisions. Flavors are extracted directly from the balanced `productFlavors { ... }` block.
- **iOS**: Parses `PRODUCT_BUNDLE_IDENTIFIER` from `project.pbxproj` and `.xcconfig` files in `ios/Flutter/`.
- **Firebase**: Checks `google-services.json` and `GoogleService-Info.plist`.

### What is detected automatically, and what do I have to enter by hand?
Autoscan detects bundle IDs, package names, flavors, and Firebase files automatically.
You must manually supply store credentials in **Configure (⚙️)**:
- Apple ID email, App Store Connect Issuer ID, and `.p8` API Key file for TestFlight.
- Google Play Service Account JSON key path for Play Store publishing.
See [Configuring App Settings](README.md#️-configuring-app-settings-via-the-ui).

### Where are the settings stored (.dev-dashboard/)? Should I commit them?
Settings are stored in `<workspace>/.dev-dashboard/` (`apps_config.json`, `deploy_config.json`, `commands_config.json`).
The dashboard automatically adds `.dev-dashboard/` to your workspace `.gitignore` on first run so credentials and local configurations are never committed by accident. If your team wishes to share config, commit `apps_config.json` while excluding secrets.

### I changed my bundle ID. Why does the console still show the old one?
Standard autoscan fills missing fields without overwriting user customizations. To refresh changed IDs from source code, click **Scan All Apps** or use **Rescan Workspace** with force-overwrite mode. The dashboard will show a diff of updated fields before saving.

---

## 4. Building and Deploying

### How do I build or upload to TestFlight or Play?
Select your app from the left sidebar, choose your target environment tab (`dev`, `qa`, `prod`, or unflavored default), and click an action card like **Build IPA**, **Upload IPA**, or **Deploy AAB**. Output streams live into the embedded terminal. Upload cards are locked until required store credentials are configured.
See [Execution & Job Lifecycle](README.md#-execution--job-lifecycle).

### Why do I get a confirmation popup for prod?
To prevent accidental releases, all production store deployment commands (`upload_ipa`, `deploy_ipa`, `upload_aab`, `deploy_aab`) trigger a mandatory safety confirmation modal. For single apps without flavors (`flavor: default`), the safety gate checks template IDs directly to ensure accidental uploads cannot occur.
See [Safety & Approval Gates](README.md#-safety--approval-gates).

### Why is my second job blocked (APP_BUSY)?
The dashboard enforces a concurrency guard: an app can only execute one job at a time. If another build is running for that app in the active workspace, new jobs are rejected with `APP_BUSY` displaying elapsed runtime. Locks are workspace-scoped so building an app in workspace A does not block the same app name in workspace B.

### Where do I see the logs and history?
Live output streams in real-time in the **Live Terminal**. Completed and historical builds are logged in the **History** tab, showing status badges, durations, command strings, error excerpts, and full terminal transcripts.
See [Deployment History](README.md#-deployment-history).

---

## 5. Security

### Is it safe to run? Can I expose it on my network or through ngrok?
The server is designed for **local use only** (`localhost` / `127.0.0.1`).
**Do not expose the port publicly or bind to 0.0.0.0 via ngrok/tunnels.** The server enforces DNS rebinding protection (rejecting non-localhost `Host` headers), origin validation, strict Content-Security-Policy headers, shell-injection quoting, and path traversal guards. Exposing it externally would risk unauthorized command execution.

### How do the webhook and its secret work?
The `/api/deployment/webhook` endpoint allows CI/CD systems or chat bots to trigger builds remotely. It requires configuring `WEBHOOK_SECRET` in `.env`. Incoming POST requests must include either `X-Webhook-Secret` or a GitHub-standard HMAC SHA256 header (`X-Hub-Signature-256`).
See [CI/CD Webhook Integration](README.md#-cicd-webhook-integration).

---

## 6. Troubleshooting

### My build fails with `--flavor dev`, but I have no flavors.
If you manually typed flavors in the Configure modal for a project without Gradle or Xcode flavors, builds will invoke `--flavor` and fail. Clear the **Flavors** field in Configure (⚙️) and save. The modal displays a warning toast if typed flavors conflict with scan results.

### My packages show Build buttons.
The discovery engine identifies a Flutter project as a deployable app only if it has `android/`, `ios/`, or `lib/main.dart`. Packages without runnable entrypoints are marked `is_package: true`, hiding mobile build and store upload buttons. If an older config cached them as apps, click **Rescan Workspace** to refresh.

### My projects aren't detected.
Ensure projects have a manifest (`pubspec.yaml`, `package.json`, `build.gradle`, or `.xcodeproj`) and are placed no more than 3 directory levels below your workspace root. Ensure directory names do not start with a dot (`.`) and are not in exclusion lists (`build/`, `.dart_tool/`, `node_modules/`, `Pods/`). Click **Rescan Workspace** to re-evaluate.

---

## 7. Known Limitations

- **Dynamic Gradle Flavors**: Flavors defined via complex Groovy loops or remote scripts that require a full Gradle evaluation cannot be detected statically; add them manually in Configure (⚙️).
- **Deep Directory Nesting (>3 Levels)**: Monorepo apps placed more than 3 levels deep from root (e.g. `a/b/c/d/my_app`) require explicit entry in `melos.yaml` `packages:` or manual path registration in Configure.
- **Localhost Execution Only**: Multi-user remote team installations are not supported out-of-the-box without a secure reverse proxy and authentication layer.
- **Fastlane iOS Signing on Linux**: iOS building and signing requires macOS with Xcode command-line tools. Linux hosts can build Android APKs/AABs and web apps, but cannot compile iOS IPAs.
