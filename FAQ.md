# Frequently Asked Questions (FAQ) 📖

Comprehensive developer guide and troubleshooting reference for the **Dev Deployment Console**.
For quickstart and installation, see [README.md](file:///home/sunil-bakale/IdeaProjects/dev-deployment/README.md). For architectural design, see [ARCHITECTURE.md](file:///home/sunil-bakale/IdeaProjects/dev-deployment/ARCHITECTURE.md). For HTTP endpoint specifications, see [docs/API.md](file:///home/sunil-bakale/IdeaProjects/dev-deployment/docs/API.md).

---

## 📑 Table of Contents

1. [Getting Started & Installation](#1-getting-started--installation)
2. [Server Management & 1-Click Launchers (Zero-Terminal Startup)](#2-server-management--1-click-launchers-zero-terminal-startup)
3. [Offline Console & Interactive Demo Mode](#3-offline-console--interactive-demo-mode)
4. [Projects, Workspace Detection & Monorepos](#4-projects-workspace-detection--monorepos)
5. [Configuration & Auto-Scanning](#5-configuration--auto-scanning)
6. [Credentials & Keys (Google Play, Apple .p8, Keystores, Firebase)](#6-credentials--keys-google-play-apple-p8-keystores-firebase)
7. [Pre-flight Diagnostics ("App Doctor")](#7-pre-flight-diagnostics-app-doctor)
8. [Certificate & Keystore Expiry Sentinel](#8-certificate--keystore-expiry-sentinel)
9. [Build Size Inspector & Asset Diffing](#9-build-size-inspector--asset-diffing)
10. [Building, Signing & Store Deployments](#10-building-signing--store-deployments)
11. [Local APK Hosting & QR Code Scan-to-Install](#11-local-apk-hosting--qr-code-scan-to-install)
12. [Saved Pipelines & Chained Workflows](#12-saved-pipelines--chained-workflows)
13. [Releases, Changelog Generation & Git](#13-releases-changelog-generation--git)
14. [Outgoing Webhooks & Team Notifications](#14-outgoing-webhooks--team-notifications)
15. [UI Architecture & developer-dashboard-ui Design System](#15-ui-architecture--developer-dashboard-ui-design-system)
16. [Security, Auth Tokens & Network Hardening](#16-security-auth-tokens--network-hardening)
17. [Troubleshooting & Common Error Solutions](#17-troubleshooting--common-error-solutions)
18. [Known Limitations](#18-known-limitations)

---

## 1. Getting Started & Installation

### What is Dev Deployment Console, and who is it for?
The Dev Deployment Console is a lightweight, self-hosted web console designed primarily for mobile engineering teams (Flutter first, with full support for React Native, native Android/iOS, and web projects). It eliminates the need to remember, construct, or type complex terminal build commands, Fastlane lanes, or Git release incantations. It lets developers:
- Build signed IPAs, APKs, and App Bundles (AAB).
- Execute pre-flight system diagnostics before kicking off lengthy builds.
- Upload directly to TestFlight and Google Play Internal Testing.
- Host APKs locally and generate QR codes for immediate wireless installation on test devices.
- Compare build archive sizes and warn if oversized uncompressed assets are packaged.
- Monitor certificate and keystore expiration dates.
- Generate automated changelogs and publish Git releases with Conventional Commit tags.

### What are the prerequisites on my system?
The deployment backend requires **Python ≥ 3.10** with **zero third-party pip dependencies** (built strictly on Python standard library modules like `http.server`, `subprocess`, `json`, `zipfile`, `hashlib`, `hmac`).

In addition, standard mobile development toolchains must be installed on your workstation:
- **Bash:** Execution shell for build and deployment scripts.
- **Flutter SDK & Dart:** Required for building Flutter apps and running the release tool.
- **JDK 17 & Android SDK:** Required for compiling Android APKs/AABs and inspecting keystores via `keytool`.
- **Xcode & CocoaPods (macOS only):** Required for compiling iOS apps (`xcodebuild`), codesigning, and simulator tests.
- **Fastlane:** Bundler/Ruby gem required for automated store uploads (`upload_to_app_store`, `upload_to_play_store`).
- **Git:** Required for version bumping, changelog compiling, and pushing release tags.

### macOS says `Python 3.10 or higher is required`. How do I resolve this?
Default macOS installations ship with Apple's system Python 3.9 in `/usr/bin/python3`. Install modern Python via Homebrew:
```bash
brew install python@3.12
```
Then start the server prioritizing Homebrew's Python:
```bash
PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH" ./start.sh
```
Or export it permanently in your `~/.zshrc` / `~/.bashrc`:
```bash
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH"
```

---

## 2. Server Management & 1-Click Launchers (Zero-Terminal Startup)

### Can I run the Deployment Console without opening a terminal and typing `./start.sh`?
**Yes!** The console provides two 1-click launchers so you never have to touch the terminal after initial setup:
1. **Desktop Shortcut Launcher (`.desktop`):**
   - Click the **Server Console badge** in the header.
   - Click **Create Desktop Shortcut**.
   - This writes `~/.local/share/applications/dev-deployment.desktop` with application icon and execution script.
   - You can then launch the Deployment Console directly from your OS Application Launcher (GNOME, KDE, macOS Launchpad/Spotlight equivalent) just like native software.
2. **Auto-Start Background Service (systemd user daemon):**
   - In the Server Console modal, click **Auto-Start on Login (systemd)**.
   - This installs `~/.config/systemd/user/dev-deployment.service` and executes `systemctl --user enable --now dev-deployment.service`.
   - The backend server will automatically start in the background when your computer boots or logs in, keeping port 18112 ready at all times.

### What is the Server Console modal in the UI?
Clicking the **Server Status Badge** (`Server: Online` / `Server: Offline`) at the top right of the dashboard opens the interactive Server Management modal. From this modal, developers can:
- View current PID, uptime, active port, and memory footprint.
- Check connection health (`/api/deployment/server/status`).
- Trigger server **Restart** or **Stop**.
- Copy terminal launcher commands or install desktop/systemd launchers.
- Switch listening ports if `18112` is occupied.

### How do I start, stop, and restart the server from CLI?
The repository provides background daemon management scripts in `features/deployment/bin/`:
```bash
# Start background daemon (writes PID to features/deployment/deployment.pid)
./features/deployment/bin/start-deployment.sh

# Check process status and log tail
./features/deployment/bin/status-deployment.sh

# Restart daemon
./features/deployment/bin/restart-deployment.sh

# Stop background daemon
./features/deployment/bin/stop-deployment.sh
```

### What if port 18112 is already in use (`Address already in use`)?
You can customize the port by setting `DEPLOYMENT_PORT`:
```bash
DEPLOYMENT_PORT=19000 ./start.sh
```
Or find and stop the existing process occupying the port:
```bash
lsof -ti :18112 | xargs kill -9
```

---

## 3. Offline Console & Interactive Demo Mode

### What happens if I open `index.html` directly in my browser when the server is not running?
If you double-click or open `file:///.../features/deployment/frontend/index.html` directly:
1. The page detects the server is offline via immediate polling against `http://localhost:18112/api/deployment/server/status`.
2. It displays the **Server Offline Welcome Banner** informing you that live builds require the local backend daemon.
3. It presents a copyable `./start.sh` snippet and automatically reconnects the moment you launch the server in the background.
4. It provides an **Explore Interactive Demo** button allowing you to test-drive all console features with sample mock data!

### What can I do in Interactive Demo Mode?
Interactive Demo Mode simulates a real enterprise Flutter monorepo with multiple apps:
- **Consumer App (`consumer_app`):** Complete with Dev, QA, and Prod flavors.
- **Rider App (`rider_app`):** Featuring custom flavors and upload configurations.
- **Simulated Builds:** Click any build command (e.g. `Build AAB (prod)`) to watch simulated live terminal logs, stage progression, and completion.
- **Simulated Pre-flight Doctor:** Run diagnostics to see pass/warn/fail badge checks and actionable fix hints.
- **Simulated Build Size Inspector:** View size comparisons (`24.2 MB (+3.8 MB, +18%) ⚠️`) and raw asset warnings.
- **Simulated Sentinel Expiry Badges:** Preview proactive alerts for certificates nearing expiration.
- **Safe Exit:** Click **Exit Demo** at any time to return to live server detection.

---

## 4. Projects, Workspace Detection & Monorepos

### Which project structures are automatically supported?
The console dynamically parses and understands six different workspace layouts out of the box with zero required configuration:
1. **Single App:** Standalone Flutter or React Native project root.
2. **Single App with Local Packages:** Root app that depends on libraries in a local `packages/` directory.
3. **Multi-App Workspace:** Monorepo with multiple independent applications in subdirectories (e.g. `apps/consumer`, `apps/driver`).
4. **Multi-App with Shared Packages:** Monorepo with multiple applications sharing internal Dart libraries without Melos.
5. **Melos Monorepo:** Managed via `melos.yaml`, automatically resolving `packages:` globs and `ignore:` exclusions.
6. **Dart Pub Workspace:** Native Dart 3.5+ pub workspaces declaring `workspace: [ ... ]` in the root `pubspec.yaml`.

### How does the system distinguish deployable apps from non-deployable packages?
When scanning directories:
- A folder is classified as a **Deployable App** if it contains `android/`, `ios/`, or `lib/main*.dart`, AND does NOT declare `flutter: plugin:` in its `pubspec.yaml`.
- A folder is classified as a **Non-Deployable Package** if it is a pure Dart library, Flutter plugin, or utility package. Packages are rendered in a collapsible info drawer and excluded from build command grids to prevent invalid build attempts.
- Nested `example/` directories inside packages are automatically skipped.

### How do multi-project tabs work?
You can import multiple separate git repositories simultaneously:
- Click **+ Import Project** to choose any folder on your machine.
- Each repository appears as an independent tab on the dashboard top bar.
- Project selection is scoped per browser tab via the `X-Workspace` HTTP header. Two developers or two browser windows can operate on different projects simultaneously without cross-talk.
- Removing a project tab (clicking **×**) only detaches the tab from the dashboard view; your local directory, git history, and `.dev-dashboard/` configuration are never deleted.

---

## 5. Configuration & Auto-Scanning

### Where are project settings stored? Can I commit them to Git?
Project configurations are stored inside `<project-root>/.dev-dashboard/`:
- `apps_config.json`: Detected apps, display names, file paths, framework stack, and icon metadata.
- `deploy_config.json`: Bundle IDs, Android package names per flavor, Apple Developer Account IDs, App Store Connect Issuer UUIDs, Firebase file paths, and automated post-build release flags.
- `deployment_history.jsonl`: Log of all past execution runs, durations, and exit statuses.

> [!NOTE]
> All files inside `.dev-dashboard/` store **identifiers and file paths only** — never private keys, tokens, or passwords. Committing `.dev-dashboard/` to git is safe and allows your entire engineering team to share identical flavor and bundle ID configurations.

### What does "Auto-Scan App" and "Scan All Apps" do?
Auto-Scan inspects your codebase's native files statically:
- **Android:** Parses `android/app/build.gradle` or `build.gradle.kts` to extract `applicationId`, `namespace`, and all `productFlavors`.
- **iOS:** Parses `ios/Runner.xcodeproj/project.pbxproj` and `.xcconfig` files to discover `PRODUCT_BUNDLE_IDENTIFIER` across Release and Debug configurations.
- **Firebase:** Searches for `google-services.json` and `GoogleService-Info.plist` across flavor folders.
Auto-scan fills missing fields without overwriting your manual edits.

---

## 6. Credentials & Keys (Google Play, Apple .p8, Keystores, Firebase)

### Where are sensitive keys stored on my computer?
To guarantee absolute security, **no private keys or passwords are ever stored inside the project folder**.
All imported credentials reside in your user home directory with restricted Unix file permissions (`chmod 600` / `0700`):
- **Google Play Service Account JSONs:** `~/.config/dev-deployment/keys/<key-id>.json`
- **App Store Connect API Keys (`.p8`):** `~/.appstoreconnect/private_keys/AuthKey_<KEYID>.p8`
- **Key-to-App Secure Mapping:** `~/.config/dev-deployment/credentials.json`

### Can the tool locate my existing keys automatically?
Yes. In **Configure → Keys**, click **Choose folder to scan…** (or **Scan this workspace**). The scanner reads files by **content inspection**:
- It distinguishes Google Play Publishing keys from generic Firebase Admin SDK keys.
- It identifies App Store Connect API keys by detecting `AuthKey_*.p8` naming and ECDSA PKCS#8 headers.
- It scans for `key.properties`, release keystores (`*.jks`, `*.keystore`), and Firebase configs.
Click **Import** to assign the key to one app or globally across all apps in the workspace.

### Why are iOS upload buttons disabled or locked?
iOS upload commands (`Upload to TestFlight`, `Build & Upload IPA`) require:
1. An imported App Store Connect API Key (`AuthKey_<KEYID>.p8`) with its Issuer UUID, OR
2. Valid Apple ID / App-Specific Password environment variables configured in `env/<flavor>.json` or `~/.config/dev-deployment/credentials.json`.
Once configured, the card unlocks and displays a green dot.

---

## 7. Pre-flight Diagnostics ("App Doctor")

### What is "App Doctor"?
App Doctor is a built-in pre-flight diagnostic engine that runs 12+ rigorous verification checks before starting a compilation. It catches missing tools, broken configurations, expired certs, or dirty repositories in seconds, preventing hours wasted on builds that would inevitably fail.

### What specific checks does App Doctor run?
1. **Flutter SDK:** Verifies `flutter` executable availability, version, and Dart SDK integrity.
2. **Android SDK & Java:** Checks `ANDROID_HOME`, `javac` version (JDK 17 recommended), and Gradle wrapper compatibility.
3. **Xcode & CocoaPods (macOS):** Verifies Xcode CLI tools, `pod --version`, and Podfile lock status.
4. **Fastlane:** Checks fastlane binary availability via Bundler or system gems.
5. **Git Workspace Cleanliness:** Warns if uncommitted changes or untracked files are present on release branches.
6. **Android Keystore:** Verifies keystore file existence, validity, alias presence, and expiration date via `keytool`.
7. **Apple Distribution Certificate:** Inspects Keychain or imported certs for validity and expiration within 30 days.
8. **Provisioning Profiles:** Validates matching bundle identifiers and entitlement files.
9. **App Store Connect API Key:** Verifies `.p8` key syntax, key ID length (10 chars), and Issuer UUID format.
10. **Google Play Service Account:** Validates JSON schema, client email, and private key integrity.
11. **Firebase Configuration Cross-Check:** Ensures `google-services.json` and `GoogleService-Info.plist` target the same project ID.
12. **Build Tool Cache Integrity:** Checks Gradle cache and CocoaPods cache for corrupt lockfiles.

---

## 8. Certificate & Keystore Expiry Sentinel

### What is the Certificate & Keystore Expiry Sentinel?
The Sentinel is a background monitoring subsystem designed to eliminate release day panics caused by sudden certificate expirations. It continuously inspects signing assets and displays prominent dashboard alert badges if:
- An **Apple App Store Connect API Key (`.p8`)** or **Distribution Certificate** expires within **30 days** (warning) or is expired (critical error).
- An **Android Upload Key or Keystore certificate** nears its validity limit.
- A **Firebase Project ID Mismatch** is detected (e.g. dev Firebase configuration accidentally included in a production release target).

### How do I check Sentinel details?
- If any asset requires attention, a glowing amber or red **Sentinel Alert** badge appears in the dashboard top bar.
- Clicking the badge opens the Sentinel Inspection Drawer displaying days remaining, expiration dates, cert fingerprints, and direct links to update keys.

---

## 9. Build Size Inspector & Asset Diffing

### How does the Build Size Inspector work?
Every time an APK or App Bundle (AAB) is generated, the backend automatically analyzes the archive:
- **Pure Python Zip Inspection:** Reads the ZIP Central Directory structures directly without decompressing gigabytes of files onto disk.
- **Delta Calculation:** Compares output byte size against the previous successful run of the same flavor and platform.
- **Visual Badge:** Displays output like `AAB: 24.2 MB (+3.8 MB, +18%) ⚠️`.

### Why does it warn about uncompressed raw assets (`ZIP_STORED`)?
Android App Bundles compress assets using DEFLATE. If a developer accidentally adds huge uncompressed files (e.g. raw 4K videos, uncompressed test databases, or heavy JSON datasets) using `ZIP_STORED` (compression method 0) exceeding **500 KB**, the Build Size Inspector flags them immediately with a list of offending filenames so they can be optimized before shipping to users.

---

## 10. Building, Signing & Store Deployments

### How do I trigger a build or deployment?
1. Select your project tab.
2. Select your target application tile.
3. Select your target environment: **Dev**, **QA**, or **Prod**.
4. Click any command tile (e.g. `Build & Upload AAB (qa)`).
5. The exact command is displayed in the **Ready to Execute** box.
6. Click **Run**. Live output streams into the integrated **Live Terminal**.

### Which Google Play track receives uploads?
By default, the automated Fastlane lane publishes to the **Internal Testing** track (`track: 'internal'`) to ensure all builds undergo automated Google Play pre-launch reports before human review.

### Why do I see a confirmation popup before running Prod builds?
Production store upload commands are protected by safety confirmation guards. A modal dialog displays the full command line and requires explicit confirmation to prevent accidental production releases.

### Can two builds run at the same time?
- **Same App:** Blocked with error code `APP_BUSY` to prevent lock contention and corrupted build caches.
- **Different Apps (or different projects):** Fully supported in parallel!

---

## 11. Local APK Hosting & QR Code Scan-to-Install

### How does the QR code scan-and-install feature work?
When an Android APK build finishes successfully:
1. The backend exposes the generated `.apk` under `/api/deployment/download/<job_id>`.
2. An **Android APK Ready** banner appears above the terminal.
3. Clicking **Scan to Install** opens a modal with a generated SVG QR Code and direct download button.
4. Developers and QA testers can connect their physical Android devices to the same local Wi-Fi, open the default camera app, scan the QR code, and download/install the APK immediately — no USB cables, ADB commands, or Firebase App Distribution invites required!

### Why does scanning the QR code fail on my phone?
Ensure:
1. Your test device is connected to the same local Wi-Fi network as your host workstation.
2. Your host firewall allows incoming connections on port 18112.
3. If running on Linux/macOS with multiple network adapters, ensure the IP shown in the QR code matches your LAN Wi-Fi adapter (configure `HOST_OVERRIDE` or `--host` if needed).

---

## 12. Saved Pipelines & Chained Workflows

### What are Saved Pipelines?
Saved Pipelines allow developers to chain multiple independent deployment steps into an automated, sequential pipeline (e.g., `1. App Doctor Diagnostics` → `2. Run Tests` → `3. Build Release AAB` → `4. Upload to Google Play` → `5. Post Webhook Notification`).

### What happens if a pipeline step fails?
Pipelines feature strict **Stop-on-Failure** safety semantics:
- If step 1 fails, step 2 and subsequent steps are immediately marked as **Skipped**.
- The pipeline execution halts, releasing the app busy lock and logging the step that caused the failure.

---

## 13. Releases, Changelog Generation & Git

### How does the automated release tool generate changelogs?
The release tool (`release_changelog_tagger.dart`) parses the git log since the previous release tag:
- It categorizes commits according to the **Conventional Commits** specification:
  - `feat(...)`: Features
  - `fix(...)`: Bug Fixes
  - `perf(...)`: Performance Improvements
  - `refactor(...)`: Code Refactoring
  - `chore(...)`, `ci(...)`, `docs(...)`: Maintenance
- It automatically attributes contributors and formats output into `CHANGELOG.md`.

### What is the recommended release sequence?
1. Click **1. Preview Changelog**: Review the generated changelog and commit list without making changes.
2. Click **6. Bump Version (Patch)** (or Minor/Major): Updates `pubspec.yaml`, appends release notes to `CHANGELOG.md`, and creates local Git commit and tag.
3. Click **5. Full Release (Push)**: Pushes the release branch and annotated tag to `origin`.

### Why does Full Release fail with "Tag already exists"?
This occurs if the version declared in `pubspec.yaml` was already tagged in git. Bump the version first (using action 6, 7, or 8) before running Full Release.

---

## 14. Outgoing Webhooks & Team Notifications

### Which platforms are supported for team build notifications?
The webhook engine supports rich formatted notifications to:
- **Slack:** Block Kit formatted message cards.
- **Discord:** Embed cards with status colors.
- **Microsoft Teams:** Adaptive card layouts.
- **Google Chat:** Card v2 format.

### What details are included in the notification card?
Notifications include:
- App Name and Flavor (`QA` / `Production`).
- Build Status: Success (green), Failure (red), or Stopped (amber).
- Job duration (e.g. `2m 45s`).
- Git commit hash, branch, and author.
- Direct download link and QR scan button for mobile test devices (when APK is produced).

---

## 15. UI Architecture & developer-dashboard-ui Design System

### Where does the styling and CSS design system come from?
The user interface is built on **`developer-dashboard-ui`**, a universal, standalone design system located in `frontend/developer-dashboard-ui/`.
- All visual components (`.ui-button`, `.ui-badge`, `.ui-card`, `.ui-alert`, `.ui-modal`, `.ui-segmented-control`, `.ui-terminal`, `.ui-grid`, `.ui-page-shell`) adhere strictly to the design system.
- No bespoke CSS overrides or ad-hoc stylesheets are placed in application folders.
- CSS is bundled into `frontend/developer-dashboard-ui/dist/ui.css` via `python3 bundle.py`.

### How does the frontend handle offline loading?
The stylesheet loader in `index.html` implements progressive fallbacks:
1. Primary: Local bundled stylesheet `../../../frontend/developer-dashboard-ui/dist/ui.css`.
2. Fallback 1: Local HTTP server route `/developer-dashboard-ui/dist/ui.css`.
3. Fallback 2: Fast global jsDelivr CDN (`https://cdn.jsdelivr.net/gh/sunilbvb/developer-dashboard-ui@main/dist/ui.css`).

---

## 16. Security, Auth Tokens & Network Hardening

### Can the deployment server be accessed across the internet?
**No. By design, the deployment server is strictly bound to `localhost` (`127.0.0.1` / `::1`).**
- Any request with a non-localhost `Host` header is immediately blocked (`403 DNS Rebinding Rejected`).
- Foreign web origins are rejected via strict CORS validation.
- All REST API endpoints require a valid `X-API-Token` header.
- The random bearer token is generated on initial run with secure permissions `chmod 600` at `~/.config/dev-deployment/auth_token.txt`.
- Executed commands are strictly whitelisted from verified templates; raw shell command injection via the API is impossible.

---

## 17. Troubleshooting & Common Error Solutions

### Quick Diagnostic Matrix

| Error Message / Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| **"Could not load commands" / Red Server Badge** | Backend server is offline or crashed. | Run `./start.sh` or check `./features/deployment/bin/status-deployment.sh`. |
| **"APP_BUSY: An active job is already running"** | Previous build process is still running or hung. | Click the red **Stop** button on the active app or run `./features/deployment/bin/stop-deployment.sh`. |
| **"CocoaPods not installed or not on PATH"** | CocoaPods missing on macOS or terminal subshell has altered `PATH`. | Run `brew install cocoapods` or `gem install cocoapods`. |
| **"Service account file not found"** | Google Play publishing JSON missing from lookup paths. | In **Configure → Keys**, click **Choose folder to scan…** and import your service account JSON. |
| **"Invalid Host header: DNS rebinding rejected"** | Accessing server via custom domain or proxy without permission. | Always connect via `http://localhost:18112` or configure `ALLOWED_HOSTS`. |
| **"No package name found for flavor"** | Android `applicationId` missing from Gradle config. | Run **Auto-Scan App** in Configure → General or manually enter the package ID. |
| **"Command failed with exit code 128 (Git push)"** | SSH agent locked or permissions missing on remote. | Ensure `ssh-add` has your key loaded and verify `git push origin develop` manually. |
| **"Asset larger than 500 KB stored uncompressed"** | Large raw files packed into AAB without compression. | Optimize asset sizes or enable compression in `android/app/build.gradle`. |

---

## 18. Known Limitations

- **Dynamic Gradle Flavors:** Gradle flavors declared inside complex Groovy loops or remote scripts cannot be statically determined without executing Gradle; specify them once in **Configure → General**.
- **iOS Builds Require macOS:** Native iOS IPA compilation and codesigning require Xcode and macOS hardware.
- **Single Workstation Scope:** Designed for local developer machines and dedicated build mac-minis; multi-tenant remote hosting is intentionally disallowed for security.
- **Conventional Commit Requirement:** Automated changelog generation relies on Conventional Commit prefixes (`feat:`, `fix:`, `chore:`); non-conforming commits are grouped under maintenance.
