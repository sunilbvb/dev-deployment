# Dev Deployment Console 🚀

A lightweight, self-hosted web console to build, sign, inspect, upload and release mobile apps — Flutter first, with React Native, native Android/iOS, and web projects supported — without typing terminal commands.

Open `http://localhost:18112`, pick a project tab, select an app, choose an environment, run pre-flight diagnostics, click a build command, and watch real-time streamed logs.

> **Backend:** `features/deployment/backend/` — Pure Python standard library (no pip dependencies)  
> **Frontend:** `features/deployment/frontend/` — Vanilla JS powered by the [`developer-dashboard-ui`](frontend/developer-dashboard-ui/README.md) design system  
> **Build/Release Scripts:** `features/deployment/scripts/` — Bash + Dart Conventional Commit release engine  
> **Default Port:** `18112` (`DEPLOYMENT_PORT`)

---

## 📑 Table of Contents

1. [Key Features & Capabilities](#-key-features--capabilities)
2. [Quick Start & Launchers (Zero-Terminal Setup)](#-quick-start--launchers-zero-terminal-setup)
3. [Offline Welcome Console & Interactive Demo Mode](#-offline-welcome-console--interactive-demo-mode)
4. [Projects: Import & Independent Tabs](#-projects-import--independent-tabs)
5. [Workspace Discovery & Monorepo Support](#-workspace-discovery--monorepo-support)
6. [Configure: Per-App Settings & Auto-Scanning](#️-configure-per-app-settings--auto-scanning)
7. [Credentials: Play Keys, Apple .p8 & Keystores](#-credentials-play-keys-apple-p8--keystores)
8. [Pre-flight Diagnostics ("App Doctor")](#-pre-flight-diagnostics-app-doctor)
9. [Certificate & Keystore Expiry Sentinel](#-certificate--keystore-expiry-sentinel)
10. [Build Size Inspector & Uncompressed Asset Diff](#-build-size-inspector--uncompressed-asset-diff)
11. [Building & Store Deployments](#-building--store-deployments)
12. [Local APK Hosting & Wireless QR Code Installation](#-local-apk-hosting--wireless-qr-code-installation)
13. [Saved Pipelines (Chained Workflows)](#-saved-pipelines-chained-workflows)
14. [Releases: Conventional Commits, Changelog & Git Tags](#️-releases-conventional-commits-changelog--git-tags)
15. [Outgoing Webhooks & Team Notifications](#-outgoing-webhooks--team-notifications)
16. [Design System: developer-dashboard-ui](#-design-system-developer-dashboard-ui)
17. [Safety & Security Hardening](#️-safety--security-hardening)
18. [Configuration & Data Files](#-configuration--data-files)
19. [Environment Variables](#-environment-variables)
20. [Contributing & Documentation Index](#-contributing--documentation-index)

---

## 💡 Key Features & Capabilities

- **Automatic Project & App Discovery:** Finds apps across any repository layout: single app, multi-app, shared package monorepos, Melos monorepos, and Dart 3.5+ pub workspaces.
- **Zero-Terminal Startup:** 1-click desktop shortcut creation (`.desktop`) and systemd user login daemon to run in background automatically.
- **Interactive Offline Demo Mode:** Explore, test simulated builds, diagnostics, and size diffs without running the backend server.
- **Pre-flight "App Doctor":** 12+ diagnostic checks (Flutter SDK, Android SDK, CocoaPods, keystores, provisioning profiles, Git cleanliness, Firebase configs) catching issues before long builds.
- **Certificate & Keystore Expiry Sentinel:** Proactive alerts when Apple `.p8` keys, distribution certificates, or Android keystores expire within 30 days, or when Firebase project IDs mismatch.
- **Build Size Inspector & Diff:** Analyzes AAB/APK ZIP central directories without disk extraction. Displays deltas (`AAB: 24.2 MB (+3.8 MB, +18%) ⚠️`) and warns if raw uncompressed assets (`ZIP_STORED` ≥ 500 KB) are packaged.
- **Local APK Wireless QR Code:** Instantly host completed APKs over local HTTP and scan a QR code from any physical device on the local Wi-Fi to install without USB cables.
- **Saved Pipelines:** Chain multi-step sequences (`Doctor` → `Tests` → `Build AAB` → `Upload`) with stop-on-failure safety and live progress bars.
- **Automated Conventional Changelogs:** Generates `CHANGELOG.md`, annotated git tags, and release commits grouped by `feat:`, `fix:`, and `perf:`.
- **Zero-Dependency Backend:** Built 100% on Python's standard library. No `pip install` required.

---

## 🏁 Quick Start & Launchers (Zero-Terminal Setup)

### Prerequisites

| Tool | Purpose | Minimum Version |
|:---|:---|:---|
| **Python** | Backend server daemon | ≥ 3.10 (Standard Library only) |
| **Bash** | Build & execution shell | Standard POSIX Bash |
| **Flutter SDK & Dart** | Flutter compilation & release tagger | Flutter 3.x / Dart 3.x |
| **Xcode & CocoaPods** | iOS compilation & codesigning | macOS with Xcode 15+ |
| **JDK & Android SDK** | Android APK / AAB compilation | JDK 17 |
| **Fastlane** | App Store Connect & Google Play upload | Bundler or system gem |
| **Git** | Release commits, tags, and origin push | Standard Git |

### Start the Console

```bash
# Clone the repository
git clone -b develop https://github.com/sunilbvb/dev-deployment.git
cd dev-deployment

# Start the foreground server
./start.sh
```

If macOS ships Python 3.9, install Python 3.12 via Homebrew:
```bash
PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH" ./start.sh
```

Open `http://localhost:18112` in any modern web browser.

### 1-Click Launchers (Never Touch the Terminal Again)

Click the **Server Console badge** (`Server: Online`) in the top navigation bar to open the server management modal:
1. **Create Desktop Shortcut:** Creates `~/.local/share/applications/dev-deployment.desktop`. Launch the deployment console directly from your OS application menu or dock.
2. **Auto-Start on Login (systemd):** Installs and enables `~/.config/systemd/user/dev-deployment.service`. The server daemon starts automatically every time you log into your computer.

### Daemon Management CLI

```bash
./features/deployment/bin/start-deployment.sh    # Start in background
./features/deployment/bin/status-deployment.sh   # Check PID, uptime & logs
./features/deployment/bin/restart-deployment.sh  # Graceful restart
./features/deployment/bin/stop-deployment.sh     # Terminate background daemon
```

---

## 🧪 Offline Welcome Console & Interactive Demo Mode

Opening `features/deployment/frontend/index.html` directly (or double-clicking the file) while the backend server is stopped presents the **Offline Welcome Console**:
- Informs the developer that live builds require the local backend daemon.
- Displays an auto-reconnecting status indicator listening on port 18112.
- Provides an **Explore Interactive Demo** button that launches a full simulation:
  - Mock multi-flavor consumer and rider apps.
  - Simulated terminal output streams with progress bars.
  - Interactive Pre-flight Doctor diagnostics with sample fix recommendations.
  - Simulated build size comparisons and sentinel expiration badges.

---

## 📂 Projects: Import & Independent Tabs

1. Click **+ Import Project** in the header.
2. Choose your project directory via the native folder dialog.
3. The modal displays what was detected: directory name, layout architecture, detected apps, and non-deployable packages.
4. Click **Add Project**. It appears as a persistent tab on the top bar.

**Tab Isolation:** Each browser tab maintains its own active project context via the `X-Workspace` header. Multiple engineers or multiple browser windows can inspect and deploy different repositories simultaneously.

---

## 🔍 Workspace Discovery & Monorepo Support

The discovery engine inspects project directories up to 4 levels deep:
- **Melos Monorepos:** Automatically parses `melos.yaml` `packages:` globs and honors `ignore:` rules.
- **Dart Pub Workspaces:** Reads `workspace: [ ... ]` definitions from the root `pubspec.yaml`.
- **Apps vs Packages:** Flutter packages declaring `flutter: plugin:` or pure Dart libraries are classified as non-deployable packages, listed in a collapsible panel to keep the command grid clean.
- **Flavor Discovery:** Statically inspects Gradle `productFlavors` and iOS `.xcconfig` files to configure Dev, QA, and Prod tabs automatically.

---

## ⚙️ Configure: Per-App Settings & Auto-Scanning

Click **Configure** on any app to manage:
- **General:** App display name, custom flavors, bundle IDs, and Android package names.
- **Keys:** Association with Google Play Service Accounts, App Store Connect `.p8` keys, and keystores.
- **iOS:** Apple ID, App Store Connect Issuer UUID, and provisioning profiles.
- **Android:** Keystore path, key alias, and Play publishing tracks.
- **Firebase:** Android `google-services.json` and iOS `GoogleService-Info.plist` path mappings.
- **Auto-Scan App:** Statically inspects native files to automatically fill missing bundle IDs and flavor names without overwriting manual settings.

---

## 🔑 Credentials: Play Keys, Apple .p8 & Keystores

### Strict Security Isolation
**Zero credentials are stored in your project repository.**
All imported keys are stored in your user home folder with restricted `chmod 600` permissions:
- Google Play JSON keys: `~/.config/dev-deployment/keys/`
- App Store Connect `.p8` keys: `~/.appstoreconnect/private_keys/`
- Key mappings: `~/.config/dev-deployment/credentials.json`

### Content-Based Key Scanner
In **Configure → Keys**, click **Choose folder to scan…**. The scanner analyzes files by their cryptographic content:
- Distinguishes Google Play publishing service accounts from Firebase Admin keys.
- Recognizes `AuthKey_<KEYID>.p8` App Store Connect API keys.
- Finds keystores (`*.jks`, `*.keystore`) and reads certificate metadata.

---

## 🩺 Pre-flight Diagnostics ("App Doctor")

Click **App Doctor** to evaluate your environment before starting a build:
- **SDK Verifications:** Flutter SDK, Dart SDK, Android SDK, JDK 17, and Xcode CLI tools.
- **Build Utilities:** Fastlane Bundler status, CocoaPods podfile locks.
- **Signing Assets:** Apple `.p8` key syntax, keystore validity, and provisioning profile expiry.
- **Cross-Platform Consistency:** Confirms Android and iOS Firebase project IDs match.
- **Repository State:** Flags uncommitted changes on release branches.

---

## 🛡️ Certificate & Keystore Expiry Sentinel

The Sentinel continuously inspects signing assets and raises alerts:
- **30-Day Expiry Warnings:** Amber banner when Apple distribution certificates or `.p8` API keys expire within 30 days.
- **Keystore Alerts:** Warnings when Android release keystore validity nears its limit.
- **Firebase Mismatches:** Detects if development Firebase configs are accidentally linked to a production build target.

---

## 📦 Build Size Inspector & Uncompressed Asset Diff

Upon completion of any AAB or APK build:
- **Fast In-Memory ZIP Analysis:** Reads the ZIP Central Directory without extracting files.
- **Run-to-Run Delta:** Compares byte size against the previous successful run (`AAB: 24.2 MB (+3.8 MB, +18%) ⚠️`).
- **Oversized Raw Asset Warnings:** Flags any uncompressed assets (`ZIP_STORED`) exceeding **500 KB** to prevent bloated app releases.

---

## 🚀 Building & Store Deployments

1. Select target app and environment tab (**Dev**, **QA**, **Prod**).
2. Click the desired command tile (e.g. `Build & Upload AAB`).
3. View the generated command in the **Ready to Execute** box.
4. Click **Run**. Output streams live into the terminal.
5. **Safety Confirmation:** Production store uploads require explicit confirmation before running.
6. **Stop Job:** Click **Stop** to immediately terminate the process tree (`SIGTERM` → `SIGKILL`) and release the lock.

---

## 📱 Local APK Hosting & Wireless QR Code Installation

When an Android APK build finishes:
1. The backend immediately exposes the APK over local HTTP.
2. An **Android APK Ready** banner appears above the terminal.
3. Click **Scan to Install** to view an SVG QR code.
4. Scan the QR code with any physical test device on the same local Wi-Fi network to install the APK directly—no USB cables, ADB, or external distribution services required.

---

## ⛓️ Saved Pipelines (Chained Workflows)

Automate complex multi-stage release workflows:
- Combine steps like `App Doctor` → `Run Unit Tests` → `Build Release AAB` → `Upload to Google Play`.
- **Stop-on-Failure:** If any stage fails, all subsequent stages are automatically skipped and the app lock is safely released.
- View live step progress with animated pipeline badges.

---

## 🏷️ Releases: Conventional Commits, Changelog & Git Tags

Powered by `release_changelog_tagger.dart`:
- Groups commits by Conventional Commit prefixes: `feat:`, `fix:`, `perf:`, `refactor:`, `chore:`.
- Automatically calculates version numbers: Patch, Minor, or Major.
- Updates `CHANGELOG.md`, bumps `pubspec.yaml`, creates annotated git tags (`<app>-v<version>`), and pushes to `origin`.

---

## 🔔 Outgoing Webhooks & Team Notifications

Keep your engineering team updated on team channels:
- Supports **Slack**, **Discord**, **Microsoft Teams**, and **Google Chat**.
- Delivers status cards with duration, git commit info, build logs, and direct APK download links.
- Test webhooks directly from the configuration drawer.

---

## 🎨 Design System: developer-dashboard-ui

All dashboard styling originates from **`developer-dashboard-ui`** (`frontend/developer-dashboard-ui/`):
- Single source of truth CSS component library with 30 modular widgets.
- Zero external CSS dependencies.
- Rebundle at any time via `python3 frontend/developer-dashboard-ui/bundle.py`.

---

## 🔒 Safety & Security Hardening

- **Localhost Only:** Bound strictly to `127.0.0.1` and `::1`.
- **DNS Rebinding Protection:** Non-localhost `Host` headers are rejected (`403`).
- **CSRF Isolation:** Foreign browser origins are blocked.
- **Bearer Token Auth:** Generated on first run (`~/.config/dev-deployment/auth_token.txt`, `chmod 600`).
- **Command Whitelisting:** Arbitrary shell execution is impossible; only verified template commands can execute.

---

## 📁 Configuration & Data Files

| File | Scope | Description |
|:---|:---|:---|
| `<project>/.dev-dashboard/apps_config.json` | Project | Detected applications and framework stack |
| `<project>/.dev-dashboard/deploy_config.json` | Project | Bundle IDs, flavors, and release settings |
| `<project>/.dev-dashboard/deployment_history.jsonl` | Project | Persistent execution logs and durations |
| `~/.config/dev-deployment/auth_token.txt` | User | Local bearer API token (`chmod 600`) |
| `~/.config/dev-deployment/credentials.json` | User | App-to-credential mapping (`chmod 600`) |
| `~/.config/dev-deployment/keys/` | User | Imported Google Play service accounts |
| `~/.appstoreconnect/private_keys/` | User | Imported App Store Connect `.p8` keys |

---

## 🔧 Environment Variables

| Variable | Default | Purpose |
|:---|:---|:---|
| `DEPLOYMENT_PORT` | `18112` | Port for the deployment backend server |
| `WORKSPACE_ROOT` | Active root | Startup project shown on launch |
| `DEPLOYMENT_AUTH_TOKEN` | Auto-generated | Fixed token override |
| `DEPLOYMENT_TMP_DIR` | System tmp | Directory for ephemeral build logs |
| `WEBHOOK_SECRET` | None | Shared secret for CI webhook triggers |
| `GOOGLE_CHAT_WEBHOOK_URL` | None | Webhook URL for Google Chat notifications |

---

## 🤝 Contributing & Documentation Index

- [FAQ & Troubleshooting Reference](FAQ.md) — 18 comprehensive sections covering every question and scenario.
- [Architecture & Design Decisions](ARCHITECTURE.md) — Internal mechanics, process groups, and threading.
- [REST API Specification](docs/API.md) — Complete endpoint reference and schemas.
- [Contributing Guidelines](CONTRIBUTING.md) — Code style, pull request workflows, and test execution.
- [Security Policy](SECURITY.md) — Localhost protection and vulnerability reporting.

---

## 📄 License

[MIT](LICENSE)
