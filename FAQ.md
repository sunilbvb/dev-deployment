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
19. [Hybrid Distributed Builds (GitHub Actions + Local Parallel Matrix)](#19-hybrid-distributed-builds-github-actions--local-parallel-matrix)
20. [Mobile Automation Innovations (OTA QR, Wireless ADB, ChatOps, Profiler, Warmer)](#20-mobile-automation-innovations-ota-qr-wireless-adb-chatops-profiler-warmer)

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

### How are new developer questions added to this FAQ?
Whenever a developer or team member asks a meaningful question or clarifies system behavior, it should be directly documented in this [`FAQ.md`](file:///home/sunil-bakale/IdeaProjects/dev-deployment/FAQ.md). This establishes a continuous **living documentation** practice so knowledge is never lost in chat threads and the whole team learns together.

### What is the step-by-step end-to-end workflow for a new user in the UI?
All major capabilities are 100% operational directly within the web UI without terminal intervention:

1. **Import Workspace (Single App, Multi-App, or Melos Monorepo):**
   - Click the active workspace pill in the top header.
   - Enter your project path or use the folder inspector.
   - Click **Inspect Folder**: The backend inspects `pubspec.yaml` and `melos.yaml`, detects apps, and previews detected app chips. Click **Import Workspace** to switch.

2. **1-Click Auto-Scan (Flavors, Bundle IDs, Keystores, Config):**
   - Click the **Configure** button (top right header).
   - Click **⚡ Auto-Scan Project**: The backend automatically parses `build.gradle` (flavors, package names), `project.pbxproj` / `.xcconfig` (bundle IDs), Google Services JSON / plist files, and keystores.
   - Fields auto-fill immediately. Click **Save Config**.

3. **Generated Build Commands & Environment Tabs:**
   - Command generation triggers automatically on save.
   - Dashboard organizes commands into clean tabs (`Dev`, `QA`, `Prod`) for both Android (`build_apk`, `build_aab`, `deploy_aab`) and iOS (`build_ipa`, `deploy_ipa`).
   - Cards display status pills: **Ready** or **Locked (needs setup)**.

4. **Connect Outgoing Webhooks (Slack, Discord, Teams, WhatsApp):**
   - In **Configure** → **Notifications**, click **+ Add Channel**.
   - Select your provider (Slack, Discord, Microsoft Teams, Google Chat, or WhatsApp).
   - Enter your webhook URL and trigger filters (Success, Failure, or Both).
   - Click **Test Channel** to dispatch a live verification ping with rich card formatting.

5. **Build & Execute Saved Pipelines:**
   - In **Configure** → **Pipelines**, click **+ Create Pipeline**.
   - Pick sequenced actions from the step catalog (e.g. `App Doctor` → `Build AAB` → `Upload Play Store`) or write custom shell steps.
   - On the dashboard, click the Pipeline card and click **Run Pipeline**.
   - Production builds trigger a mandatory confirmation dialog to prevent accidental store releases.
   - Terminal streams live execution logs with step-by-step progress spinners.

6. **Git Connections & Release Automation:**
   - Pre-flight App Doctor evaluates Git working tree cleanliness before long builds.
   - Under the **Utilities** tab, run **Preview Changelog** to parse Conventional Commits since the last Git tag, bump version numbers, generate `CHANGELOG.md`, and push annotated tags to `origin`.

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

### How do I actually deploy the Dev Deployment Console onto a live production server (e.g. `https://devdeployment/index.html`)?
To deploy the console onto an internal production server or cloud build runner:

1. **Provision Server Host:**
   - Linux (Ubuntu 22.04/24.04 LTS) or macOS (if iOS Xcode builds are required).
   - Ensure Python ≥ 3.10, Git, and Nginx are installed.

2. **Clone the Repository:**
   ```bash
   sudo git clone https://github.com/sunilbvb/dev-deployment.git /opt/dev-deployment
   sudo chown -R $USER:$USER /opt/dev-deployment
   cd /opt/dev-deployment && git checkout main
   ```

3. **Install Systemd Production Service:**
   Create `/etc/systemd/system/devdeployment.service`:
   ```ini
   [Unit]
   Description=Dev Deployment Console Daemon
   After=network.target

   [Service]
   Type=simple
   User=deployer
   WorkingDirectory=/opt/dev-deployment
   ExecStart=/usr/bin/python3 features/deployment/backend/server.py --port 18112 --host 127.0.0.1
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
   Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now devdeployment
   ```

4. **Configure Nginx Reverse Proxy with HTTPS:**
   Create `/etc/nginx/sites-available/devdeployment`:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name devdeployment devdeployment.internal;

       ssl_certificate /etc/ssl/certs/devdeployment.crt;
       ssl_certificate_key /etc/ssl/private/devdeployment.key;

       location / {
           proxy_pass http://127.0.0.1:18112;
           proxy_set_header Host localhost;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
   Link and reload Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/devdeployment /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```

5. **Updating the Deployment (Zero-Downtime Rollout):**
   Because the backend is 100% Python standard library and vanilla frontend (zero `npm build`, zero `pip install`), updating is instantaneous:
   ```bash
   cd /opt/dev-deployment && git pull origin main && sudo systemctl restart devdeployment
   ```

6. **Deploying Web Applications via the Tool:**
   If your goal is to build and deploy Flutter Web, React, or static web applications to `https://devdeployment/`, create a pipeline step:
   ```bash
   flutter build web --release && rsync -av --delete build/web/ /var/www/devdeployment/
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

### How does the tool handle multiple apps in a monorepo that share the same Flutter version or Melos scripts?
The tool keeps workspace detection strictly decoupled from execution:
- Each app discovered inside `apps/` or `packages/` maintains its own dedicated entry in `.dev-dashboard/deploy_config.json` with independent package names, bundle IDs, keystores, and flavor definitions.
- When executing commands, the tool passes `-C tool/makefiles/<app>` or runs native Flutter commands directly scoped inside the specific application directory (`cwd=<app_path>`), completely avoiding build cache collisions between sibling apps.

### How does the tool ingest project data—does it use local file paths or Git URLs?
The tool is designed as a **local-first build engine**, meaning it operates directly on physical directory paths on the host workstation or build server rather than pulling in-memory Git URLs:

1. **How It Accesses Project Files:**
   - **Local Workstation:** You point to the directory where your code already lives (e.g. `/home/user/IdeaProjects/my-app` or native folder picker).
   - **Dedicated Build Server:** You clone your Git repository onto the server disk (e.g. `git clone https://github.com/org/app.git /var/repos/app`), then import `/var/repos/app` into the dashboard.

2. **Why Local Directory Paths Instead of Streaming Remote Git URLs?**
   - **Mobile Compilers Require Local Trees:** Compilers (`gradle`, `xcodebuild`, `flutter`) require a physical file system, CocoaPods symlinks, Android SDK build-tools, and platform headers.
   - **Preserves Build Caches:** Retains Gradle build caches, CocoaPods caches, and `.dart_tool/` artifacts, reducing build times from 15 minutes down to 30 seconds.
   - **Instant Edit-and-Test Workflow:** Developers can make changes in their local IDE, switch to the browser, and immediately click **Run** without being forced to commit and push untested code to GitHub.

3. **Automating Git Sync on Build Servers:**
   On a shared server, you can keep the local directory in sync with remote Git automatically by adding a pre-build step in **Saved Pipelines** (e.g., `git fetch && git checkout main && git pull origin main`) or triggering it via the incoming webhook API.

### Does the project have to be cloned on the server or machine to trigger a build?
**Yes, the code must exist on the local disk of whichever machine executes the build.**

Here is how this works in practice:

1. **When running locally on your workstation (Standard Developer Mode):**
   - **No cloning needed!** You already have your project open in your IDE.
   - The console runs directly against your active workspace directory. You make code edits, switch to the browser, and click **Run** immediately.

2. **When running on a dedicated team build server (Server / CI Mode):**
   - **Cloned to server disk once:** You run `git clone git@github.com:org/app.git /var/repos/app` on the server machine once during initial setup.
   - From then on, you never clone again. The server updates the folder automatically via `git pull` whenever a webhook or pipeline triggers.

3. **Why this is 10x faster than ephemeral cloud CI (GitHub Actions / Bitrise):**
   - **Cloud CI (Disposable VMs):** Every single run allocates a fresh VM, downloads gigabytes of SDKs, clones from scratch, and resolves all dependencies (taking 15–25 minutes).
   - **Dev Deployment Console (Persistent Local Tree):** Reuses warm Gradle caches, CocoaPods caches, and pre-resolved packages, finishing builds in **30–60 seconds**.

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

### How does the Sentinel calculate expiration dates for Apple `.p8` keys and Android `.jks` files?
- **Android Keystores:** The backend invokes the standard JDK `keytool -list -v -keystore <keystore_path>` via non-blocking subprocess, parses the `Valid from: ... until: <DATE>` certificate fields, and computes the exact remaining lifespan.
- **Apple Distribution Certificates:** On macOS, the Sentinel queries the login keychain via `security find-certificate -a -c "Apple Distribution"` and parses OpenSSL expiration attributes. If builds were previously executed, it also parses the embedded `embedded.mobileprovision` property list from the latest `.app` or `.ipa` bundle.
- **Apple .p8 Keys:** The Sentinel validates PKCS#8 syntax, key ID lengths, and checks against App Store Connect expiration limits.

---

## 9. Build Size Inspector & Asset Diffing

### How does the Build Size Inspector work?
Every time an APK or App Bundle (AAB) is generated, the backend automatically analyzes the archive:
- **Pure Python Zip Inspection:** Reads the ZIP Central Directory structures directly without decompressing gigabytes of files onto disk.
- **Delta Calculation:** Compares output byte size against the previous successful run of the same flavor and platform.
- **Visual Badge:** Displays output like `AAB: 24.2 MB (+3.8 MB, +18%) ⚠️`.

### Why does it warn about uncompressed raw assets (`ZIP_STORED`)?
Android App Bundles compress assets using DEFLATE. If a developer accidentally adds huge uncompressed files (e.g. raw 4K videos, uncompressed test databases, or heavy JSON datasets) using `ZIP_STORED` (compression method 0) exceeding **500 KB**, the Build Size Inspector flags them immediately with a list of offending filenames so they can be optimized before shipping to users.

### How does the Build Size Inspector inspect archives without extracting them to disk?
The inspector uses Python's standard `zipfile.ZipFile` in read-only mode to parse only the **ZIP Central Directory** located at the end of the `.apk` or `.aab` file:
- It reads uncompressed and compressed byte lengths, CRC32 checksums, and compression method headers (`0` for `ZIP_STORED`, `8` for `ZIP_DEFLATED`) in milliseconds without unpacking the archive into a temporary folder.
- It extracts the file list, sorts assets by compressed size, and matches filenames against the previous build run to produce the exact file-level diff table displayed in the modal.

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

### Can QA testers scan the QR code if their mobile devices are on cellular data instead of Wi-Fi?
The default QR code serves files over your workstation's local LAN IP (e.g. `http://192.168.1.50:18112`), which requires the test phone to be on the same Wi-Fi network. If testers are remote or on cellular data:
1. Expose port 18112 securely using a reverse proxy or tunnel (such as `cloudflared tunnel` or `ngrok http 18112`).
2. Pass `--host <public-tunnel-domain>` or set `HOST_OVERRIDE` so the QR code and download links automatically generate public HTTPS URLs.
3. Alternatively, use the automated Fastlane lane to upload directly to Firebase App Distribution or Google Play Internal Testing.

---

## 12. Saved Pipelines & Chained Workflows

### What are Saved Pipelines?
Saved Pipelines allow developers to chain multiple independent deployment steps into an automated, sequential pipeline (e.g., `1. App Doctor Diagnostics` → `2. Run Tests` → `3. Build Release AAB` → `4. Upload to Google Play` → `5. Post Webhook Notification`).

### What is the Visual Pipeline Builder UI?
The Visual Pipeline Builder allows you to construct and customize workflows visually without editing raw JSON files:
- **Interactive Step Picker:** Click **+ Add Step** to open a categorized modal (`Build`, `Test`, `Release`, `Custom`) and select pre-configured command actions.
- **Custom Shell Steps:** Add arbitrary bash commands (e.g., `flutter test && dart run build_runner build`) that run directly inside the application's root directory.
- **Step Reordering:** Drag or reorder steps sequentially.
- **Continue on Failure:** Individual steps can be toggled to continue even if the step encounters a non-zero exit code (useful for test reporting or linting).

### What happens if a pipeline step fails?
Unless a step explicitly has "Continue on failure" enabled:
- If a step fails, all subsequent steps are immediately marked as **Skipped**.
- The pipeline execution halts, releasing the exclusive app busy lock and logging the exact step and output that caused the failure.

### What happens if a pipeline step fails—can I re-run only the failed step?
- When a step fails without "Continue on Failure", the pipeline immediately stops, logs the exit code and stderr, and releases the execution lock.
- While the pipeline itself records the failed state in history, you can immediately re-run the specific failed action as a standalone command from the main dashboard command grid to debug the issue.
- Once fixed, you can re-trigger the pipeline or duplicate it in the Visual Pipeline Editor to test specific stages.

---

## 13. Releases, Changelog Generation & Git

### How do I connect Git with this tool?
Git requires **zero setup or credentials configuration** within the console itself:
1. **Automatic Local Integration:** Because the deployment server runs locally under your user account, it automatically uses your workstation's `git` binary, existing SSH keys (`~/.ssh`), and Git credential helpers. Any imported project with a `.git` folder is connected immediately.
2. **Pre-flight Git Diagnostics:** App Doctor runs `git status --porcelain` and `git rev-parse --abbrev-ref HEAD`, warning if uncommitted files exist or if you are in a detached `HEAD` state before triggering builds.
3. **Automated Tagging & Remote Pushes:** The release tool (`release_changelog_tagger.dart`) parses Conventional Commits, bumps version tags in `pubspec.yaml`, writes `CHANGELOG.md`, creates annotated Git tags, and pushes commits and tags to your remote `origin` repository using your local Git credentials.
4. **Remote Git Triggering (GitHub / GitLab CI):** To trigger builds automatically when developers push code or merge PRs on GitHub, configure a repository webhook pointing to `http://<HOST>:18112/api/deployment/webhook/incoming/github` with a matching `WEBHOOK_SECRET`.

### How does the tool access private Git repositories—does it ask for Git permissions?
**No. The tool never asks for or stores your GitHub passwords, personal access tokens (PATs), or OAuth scopes.**

Because the tool executes standard system `git` commands (`git pull`, `git fetch`, `git push`) locally under your workstation or server user account, it automatically inherits your machine's existing Git authentication:

1. **SSH Keys (`git@github.com:...`):**
   If you have an SSH key configured in `~/.ssh/id_ed25519` or `~/.ssh/id_rsa` added to your GitHub account (or a Deploy Key on your build server), Git authenticates transparently without user intervention.
2. **GitHub CLI (`gh`):**
   If you use the GitHub CLI (`gh auth login`), Git's credential helper automatically authenticates private repository operations.
3. **OS Credential Manager / Keychain (HTTPS):**
   If you cloned via HTTPS (`https://github.com/org/private-repo.git`), Git retrieves the stored token from your OS Keychain (macOS Keychain, Linux `libsecret` / `git-credential-cache`, or Git Credential Manager).
4. **On a Dedicated Build Server:**
   Add a read-only or read-write **GitHub Deploy Key** in your GitHub repository settings under **Settings → Deploy Keys**, and attach the private key to the server's `~/.ssh/config`. Once the server can run `git pull` from the terminal, the Deployment Console can sync it automatically.

This zero-credential design is significantly safer: your private GitHub credentials never pass through web forms or get saved in plaintext dashboard config files.

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

## 14. Outgoing Webhooks & Universal CI/CD Ingestion

### Does the console support Slack, Discord, Microsoft Teams, and other platforms for webhooks?
**Yes, absolutely.** The tool provides complete bidirectional webhook support:

1. **Outgoing Notifications (Team Delivery Alerts):**
   - **Slack:** Interactive Block Kit cards with status emojis, build duration, flavor tags, Git commit hash/author, and direct `📱 Download APK` interactive buttons.
   - **Discord:** Rich Embeds with color status bars (green for success, amber for stopped, red for failure), build size summaries, and clickable markdown install links.
   - **Microsoft Teams:** Office 365 Connector MessageCard format with structured key-value fact lists and OpenURI action buttons.
   - **Google Chat:** Cards v2 format with structured widgets and commit metadata.
   - **WhatsApp:** Push notifications via Meta Cloud API or Twilio for on-call release leads.
   - **Custom Payload Templates & Generic JSON:** Customizable payload formatting with runtime variable interpolation (`{appName}`, `{flavor}`, `{status}`, `{duration}`, `{downloadUrl}`, `{track}`, `{commitHash}`).

2. **Incoming Webhooks (Remote CI/CD & ChatOps Triggering):**
   - **GitHub Actions & GitLab CI:** Trigger parameterized builds from remote pipelines via signed POST requests.
   - **Slack Slash Command:** Trigger builds directly from Slack channels using `/deploy <app> <flavor> <command>`.
   - **cURL / HTTP APIs:** Automated triggers from any terminal or orchestration system.

3. **Multi-Channel Dispatch:**
   - Configure multiple channels per app or across the workspace (e.g. notify Slack `#engineering` AND Discord `#qa-builds` simultaneously).

### Which platforms are supported for team build notifications?

### Can I broadcast build notifications to multiple channels simultaneously?
**Yes!** The **Multi-Destination Webhook Channels** system allows configuring as many outgoing channels as needed per application (e.g., `#dev-releases` on Slack, `#ops-alerts` on Discord, and an on-call WhatsApp number), alongside a workspace-level default fallback. Each channel can be enabled/disabled independently and filtered for Success, Failure, or both.

### How do I configure WhatsApp notifications?
1. Open **Configure** → **Notifications** → **+ Add Channel**.
2. Select **WhatsApp (Meta Cloud API / Twilio / Gateway)** as the provider.
3. Enter your webhook endpoint URL (e.g., Meta Graph API `https://graph.facebook.com/v18.0/<PHONE_NUMBER_ID>/messages` or Twilio).
4. Enter the recipient mobile number in E.164 international format (e.g. `+1234567890`).
5. Add your Bearer authorization token under **Custom HTTP Headers** (`Authorization: Bearer <META_ACCESS_TOKEN>`).
6. Click **Test Channel** to verify delivery.

### How does the Custom Payload Template engine work?
When using **Custom Payload Template**, you write any custom JSON or plain text and interpolate dynamic runtime variables:
- `{appName}`: Application display name
- `{version}`: Version tag from `pubspec.yaml`
- `{buildNumber}`: Build increment
- `{flavor}`: Environment flavor (`dev`, `staging`, `prod`)
- `{platform}`: Operating system target (Android, iOS)
- `{status}`: Outcome (`SUCCESS`, `FAILED`, `STOPPED`)
- `{duration}`: Human-readable elapsed time (`1m 45s`)
- `{downloadUrl}`: Local APK over-the-air installation link
- `{track}`: Play Console or TestFlight track name
- `{commitHash}`: Git commit hash of the build
- `{error}`: Truncated error excerpt if the build failed

You can also pass custom HTTP headers (such as `Authorization: Bearer <TOKEN>` or `X-Custom-Auth: key`) directly in the channel configuration.

### How do I trigger builds or pipelines from GitHub Actions, GitLab CI, or Slack?
Send an HTTP POST request to `/api/deployment/webhook/incoming`:
1. **GitHub Actions:** Set `WEBHOOK_SECRET` in repo secrets. Add a step using cURL or repository webhook dispatch with header `X-Hub-Signature-256` or `X-Webhook-Secret`.
2. **GitLab CI:** Add a webhook or curl job sending header `X-Gitlab-Token: $WEBHOOK_SECRET`.
3. **Slack Slash Command:** Configure a `/deploy` command in Slack pointing to `http://<HOST>:18112/api/deployment/webhook/incoming/slack`. Users can run `/deploy my_app prod build_aab` or `/deploy pipeline full_release my_app` directly in Slack channels!
4. **cURL:**
   ```bash
   curl -X POST "http://localhost:18112/api/deployment/webhook/incoming" \
     -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"app": "my_app", "pipeline": "full_release", "flavor": "prod"}'
   ```

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

### Can I deploy this console as a centralized team build server (e.g. `https://devdeployment/index.html`)?
**Yes, absolutely.** Deploying the console as a centralized build server for your engineering and QA teams is a common, highly effective pattern:

#### 1. Why Teams Deploy It on a Central Server
- **Powerful Shared Hardware:** Fast parallel compilations on a high-core build machine (e.g., Apple Silicon Mac Studio or multi-core Linux VM).
- **Centralized Signing Credentials:** Keystores, Apple `.p8` keys, and Play Store service accounts stay protected on the secure server; developers don't need sensitive production keys on personal laptops.
- **Always-Online Incoming Webhooks:** Accessible via a static internal URL (`https://devdeployment/api/deployment/webhook/incoming`) to receive GitHub Actions, GitLab CI, or Slack slash commands 24/7.
- **Zero-Friction QA Distribution:** QA testers anywhere on the corporate VPN can open `https://devdeployment/` and scan the QR code or click the direct APK download link.

#### 2. How to Set It Up with HTTPS & Reverse Proxy
1. **Choose Server Hardware:**
   - **For iOS & Android:** Use an Apple Silicon macOS machine (Mac Mini / Mac Studio) because Xcode requires macOS.
   - **For Android only:** Any Ubuntu/Debian Linux VM or server works perfectly.
2. **Run Backend Service:**
   - Install the systemd user service (Linux) or launchd daemon (macOS) via `./start.sh` or the UI Server Console modal.
   - Bind to local port `18112`: `python3 features/deployment/backend/server.py --port 18112 --host 127.0.0.1`.
3. **Configure Nginx or Caddy Reverse Proxy:**
   Set up Nginx to terminate SSL/TLS (`https://devdeployment`) and reverse proxy to the backend:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name devdeployment devdeployment.internal;

       ssl_certificate /etc/ssl/certs/devdeployment.crt;
       ssl_certificate_key /etc/ssl/private/devdeployment.key;

       location / {
           proxy_pass http://127.0.0.1:18112;
           proxy_set_header Host localhost;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
### Where should we host our build server? (Hardware & Hosting Decision Matrix)

The choice of where to host your build server depends on two factors: **whether you need iOS builds** and **whether your team has a physical office or is 100% remote**.

```
                Do you need to build iOS apps?
                         /           \
                       YES            NO (Android only)
                      /                 \
        Does team have office?         Standard Linux Cloud VPS
              /          \             (Hetzner / DigitalOcean / AWS)
            YES           NO           Cost: $15–$30/mo
            /              \
  Office Mac Mini      Cloud Dedicated Mac
  (Apple Silicon M2/M4) (Scaleway / MacStadium)
  Cost: $599 one-time   Cost: ~$60–$100/mo
  (RECOMMENDED)
```

#### Detailed Hosting Options Comparison:

| Hosting Option | Target Platform | Upfront / Monthly Cost | Build Speed | Best Suited For |
| :--- | :--- | :--- | :--- | :--- |
| **1. On-Premise Mac Mini (Office / Lab)** *(RECOMMENDED)* | iOS + Android | ~$599 one-time purchase<br>(**$0/month**) | ⚡⚡ **Blazing Fast** (Hot M2/M4 silicon caches, 30–60s builds) | **Hybrid or in-office teams.** Zero recurring cloud bills. Instant 1 Gbps Wi-Fi QR APK installs for QA phones. Remote staff connect via Tailscale VPN. |
| **2. Cloud Dedicated Mac (Scaleway / MacStadium)** | iOS + Android | $0 upfront<br>(**~$60 – $100/month**) | ⚡ **Fast** (Bare metal Apple Silicon in cloud datacenter) | **100% remote teams with no physical office.** 24/7 uptime, static cloud IP, managed power and cooling. |
| **3. Cloud Linux VPS (Hetzner / DigitalOcean / AWS)** | **Android only**<br>*(Cannot build iOS)* | $0 upfront<br>(**~$15 – $30/month**) | ⚡ **Fast** (4–8 vCPUs, 16 GB RAM) | **Android-only projects.** Cheap, fast provisioning. Cannot compile Xcode or sign iOS IPAs. |
| **4. Existing Developer Workstation** | iOS + Android | **$0** (zero cost) | ⚡⚡ **Fast** | **Solo devs or small 2–3 person teams.** Run locally during work hours. |

#### How Remote Teams Connect Securely Without Exposing Public IPs:
Never expose port 18112 directly to the open internet. Instead:
1. **Install Tailscale or WireGuard (Free):** Install Tailscale on the build server and on developer/QA laptops/phones.
2. **Access via Private Mesh IP:** The server receives a private 100.x.y.z IP accessible only to authenticated team members.
3. **No Port Forwarding Required:** Works seamlessly behind office NAT, corporate firewalls, and home routers.

### If we build our own build server for client projects, how is it secured compared to Codemagic and Bitrise?
Building your own internal build server is **often significantly more secure than public cloud CI** for client and enterprise projects. Here is how security is enforced across all layers:

1. **True Data Sovereignty (Zero Third-Party Code Exposure):**
   - **Codemagic / Bitrise:** Client intellectual property, proprietary algorithms, and App Store signing keys must be transmitted to third-party commercial cloud infrastructure.
   - **Private Build Server:** Client source code and private keystores **never leave your organization's infrastructure**. This directly satisfies strict client NDAs, SOC 2, ISO 27001, HIPAA, and banking security requirements.

2. **Network Perimeter & VPN Shielding:**
   - The build server does not have a public IP and is never exposed directly to the internet.
   - Access is restricted exclusively to authenticated employees via your corporate VPN (WireGuard, Tailscale, OpenVPN) or office LAN.
   - Host firewall (`ufw` on Linux, `pf` on macOS) drops all unauthenticated inbound traffic.

3. **Multi-Client Repository Isolation:**
   - **Granular GitHub Deploy Keys:** Each client repository uses its own distinct, scoped SSH Deploy Key (`~/.ssh/config` per host/repo). A key for Client A cannot access Client B's codebase.
   - **File System Permissions:** Projects and keys reside in separated directories with Unix file permissions (`chmod 700 /var/repos/client-a`, `chmod 600 ~/.config/dev-deployment/keys/*`), preventing cross-project inspection.

4. **Zero-Trust Backend Application Hardening:**
   - **Bearer Auth Tokens:** Mutating API calls require `X-API-Token` generated securely with `chmod 600` permissions.
   - **DNS Rebinding Protection:** Rejects unauthorized `Host` headers (`403 DNS Rebinding Rejected`).
   - **Strict Template Whitelisting:** Raw shell commands cannot be injected via API; the backend only executes pre-approved, parameterized command templates.
   - **Path Traversal Guards:** Downloads and artifact retrievals strictly validate canonical paths within designated workspace boundaries.

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

### Can I deploy the Dev Deployment Console to Netlify, Vercel, or serverless hosts?
**No for full app; only static offline demo mode can be hosted.**

- **Why full deployment fails:** The console is a local build orchestrator requiring persistent Python backend (`http.server`), direct access to local project files, and native build toolchains (Flutter SDK, Android SDK/JDK, Xcode, Fastlane, Git). Netlify and Vercel are static/serverless platforms with ephemeral containers, strict execution limits (10–26s timeout), and zero mobile build SDKs.
- **What CAN run on Netlify:** The static frontend (`features/deployment/frontend/`) can be deployed to showcase the UI in offline demo mode (mock builds, simulated diagnostics).
- **Recommended setup for remote access:** Run console on local machine or dedicated Mac Mini / Linux server, then expose dashboard securely via **Tailscale**, **Cloudflare Tunnel**, or **ngrok**. For cloud compiling, use built-in **GitHub Actions (Cloud CI)** integration.

### Can we host and run the Dev Deployment Console on GCP (Google Cloud Platform)?
**Yes for Android and Web on Compute Engine VMs, but NO for iOS.**

- **GCP Compute Engine (Ubuntu/Debian VM):**
  - **Works:** Spin up a Linux VM (e.g. `c2-standard-8`), install Python 3.10+, Flutter SDK, Android SDK, and JDK 17. Clone your repo and run `./start.sh`. Access the console dashboard via private VPC / IAP (Identity-Aware Proxy) or Cloudflare Tunnel. Full support for Android builds (`build_apk`, `build_aab`), Play Store uploads, pre-flight diagnostics, and size diffs.
  - **Limitation:** GCP does **not** provide macOS virtual machines. iOS builds (`xcodebuild`, `.ipa` compilation, App Store upload) cannot run on GCP.
- **GCP Cloud Run / Cloud Functions (Serverless):**
  - **Not recommended:** Docker container images with Flutter + Android toolchains exceed 15–20 GB. Cold starts and lack of persistent local disk caches wipe Gradle and pub caches, causing every build to take 15–25 minutes.
- **Cost comparison:** A high-performance GCP VM (8 vCPU, 32GB RAM) costs ~$120–$180/month to run continuously, compared to $0 for an existing local developer machine or office Mac Mini (which handles both iOS and Android).

### Are there Docker possibilities for the Dev Deployment Console?
**Yes! Docker is great for Android & Web containerization, but cannot compile iOS.**

- **All-in-One Android & Web Build Container:**
  - Build on top of `ghcr.io/cirruslabs/flutter:latest` (pre-loaded with Flutter, Android SDK, and OpenJDK).
  - Install Python 3.10+ and copy `dev-deployment`.
  - Mount host project directory into `/workspace` and map port `18112:18112`.
  - Mount `~/.gradle` and `~/.pub-cache` volumes so builds stay blazing fast across container restarts.
  - Keeps host machine completely clean from JDK, Gradle, and Android SDK pollution.
- **Limitation (NO iOS):**
  - Docker containers run on Linux. Xcode requires macOS. Native iOS `.ipa` compilation is impossible inside Docker.




### How do cloud CI services like Codemagic and Bitrise do it?
Cloud CI platforms (Codemagic, Bitrise, CircleCI) operate under a **multi-tenant disposable runner model**:

1. **OAuth GitHub App Integration:**
   - You grant their cloud service an OAuth app or GitHub App installation with full `repo` read/write access.
   - Their cloud servers listen for GitHub push and pull-request webhooks.

2. **Ephemeral (Disposable) Virtual Machines:**
   - On every build, their scheduler provisions a brand-new virtual machine or container (AWS EC2 Mac, Google Cloud, or Hetzner Mac bare metal).
   - The VM generates a temporary access token and executes a **cold `git clone` from scratch** onto its fresh disk.
   - It downloads the Flutter SDK, Android command-line tools, CocoaPods, and dependencies.
   - Once the `.ipa` or `.aab` is built and uploaded, **the entire VM is destroyed and wiped** to ensure security between different customers.

3. **Detailed Architectural Comparison:**

| Feature | Cloud CI (Codemagic / Bitrise) | Dev Deployment Console |
| :--- | :--- | :--- |
| **Hosting Model** | Multi-tenant public cloud | Single-tenant local machine or private team server |
| **Git Ingestion** | Cold `git clone` from scratch on each build | Persistent local disk tree (instant incremental `git pull`) |
| **Build Duration** | **15 – 25 minutes** (VM spin-up, cold clone, dependency downloads) | **30 – 60 seconds** (hot Gradle, CocoaPods, and `.dart_tool/` caches) |
| **Cost** | $50 – $300+/month per concurrent build slot | **$0** (zero subscriptions; uses your existing hardware) |
| **Offline Capability** | ❌ None (fails without active internet) | **✓ 100% offline** (works without internet, on planes or air-gapped LANs) |
| **Secret & Code Privacy** | Source code, keystores, and `.p8` keys uploaded to third-party cloud | Source code and private keys never leave your workstation/server |

---

## 19. Hybrid Distributed Builds (GitHub Actions + Local Parallel Matrix)

### Can I build Android on GitHub Actions while building iOS locally to cut build time in half?
**Yes! This is the Hybrid Distributed Build pattern.**

Instead of running iOS and Android sequentially on a single workstation (taking 15 min + 15 min = **30 minutes**):
```
Sequential Local (Traditional):
[----- 15m iOS Build -----][----- 15m Android Build -----]  --> Total: 30 minutes

Hybrid Parallel (Recommended):
[----- 15m iOS Build (Local Mac) -----]                     --> Total: 15 minutes (50% faster!)
[----- 12m Android Build (GitHub Actions Cloud) -----]
```

### Why is this idea brilliant?
1. **50% Wall-Clock Time Reduction:** Both builds compile simultaneously in parallel. Total wait time drops from 30 minutes down to ~15 minutes.
2. **Zero Cloud macOS Surcharges:** GitHub Actions charges **10x higher minute rates** for macOS runners. By compiling iOS locally on your Apple Silicon Mac and offloading only Android to GitHub's free/cheap standard Ubuntu Linux runners (2,000–3,000 free minutes/mo), your cloud bill is **$0**.
3. **Local Machine Hardware Relief:** Compiling heavy Gradle daemons and Xcode simultaneously on a single laptop causes severe thermal throttling, 100% CPU lockups, and RAM exhaustion. Offloading Android to GitHub leaves 100% of your local machine's CPU and RAM dedicated to Xcode.

### How does the tool trigger and manage GitHub Actions?
1. **GitHub `workflow_dispatch` API or `gh` CLI:**
   - The deployment tool can dispatch a GitHub Actions workflow using Python's standard `urllib.request`:
     ```bash
     curl -X POST \
       -H "Authorization: Bearer $GITHUB_PAT" \
       -H "Accept: application/vnd.github+json" \
       https://api.github.com/repos/:owner/:repo/actions/workflows/build-android.yml/dispatches \
       -d '{"ref":"develop", "inputs":{"flavor":"prod", "upload":"google_play"}}'
     ```
   - Or if GitHub CLI (`gh`) is installed locally:
     `gh workflow run build-android.yml -f flavor=prod`
### How do I configure and use Hybrid Parallel Builds in the UI?
1. **Configure GitHub Access (One-time setup):**
   - Click **Configure (⚙️)** in top navigation bar.
   - Click the **Cloud CI** tab.
   - Enter your GitHub Personal Access Token (PAT with `repo` or `actions:write` scope) and click **Save Cloud CI Settings**. (If you use the `gh` CLI locally, the tool auto-detects your auth token!).
   - Click **Install .github/workflows/deploy-android.yml** to add the automated Android compilation workflow to your project.
2. **Execute with Runner Selector:**
   - Select your target project and choose any Android build tile (e.g. `Build AAB`, `Build APK`, `Build & Upload AAB`).
   - Notice the **Execution Runner** toggle in the Ready to Execute panel:
     `[ 💻 Local Machine ]  [ ☁️ GitHub Actions ]`
   - Select **☁️ GitHub Actions** and click **Run**.
   - The live terminal streams GitHub Actions dispatch and runner status in real time.
3. **Run Parallel iOS Build Simultaneously:**
   - While the Android cloud job is running on GitHub Actions, select an iOS command (e.g. `Build IPA (prod)`).
   - Click **Run** on **Local Machine**.
   - **Both jobs execute in parallel** with zero lock contention!
   - When the GitHub Actions Android build completes, the tool automatically downloads the APK artifact and displays the **QR Code Scan-to-Install** banner for QA testers.

---

## 20. Mobile Automation Innovations (OTA QR, Wireless ADB, ChatOps, Profiler, Warmer)

Here are the high-impact mobile automation features built into the Dev Deployment Console to eliminate daily engineering bottlenecks:

### 1. Instant iOS Over-the-Air QR Install (Bypass 25-Minute TestFlight Wait) 🍎
- **Status:** **Implemented & Fully Operational** ✓
- **The Problem:** TestFlight takes 15 to 30 minutes just for Apple to "process" an uploaded build before QA testers can install it.
- **The Solution:** For development and ad-hoc builds signed with team devices, the backend serves Apple's native `itms-services://?action=download-manifest&url=...` protocol over HTTPS.
- **Technical Mechanics:**
  - **Endpoints:**
    - `GET /api/deployment/ipa-info?app=<app>&flavor=<flavor>`: Inspects recent iOS builds and returns IPA artifact metadata, direct download URL, and `itms-services://` URI.
    - `GET /api/deployment/download-ipa/<target>?token=<auth_token>`: Streams the compiled `.ipa` binary with chunked range support and token authentication.
    - `GET /api/deployment/ota/manifest.plist?app=<app>&flavor=<flavor>&token=<auth_token>`: Dynamically generates Apple's XML property list (`manifest.plist`) declaring app bundle identifier, bundle version, title, and asset download URL.
  - **The Magic:** QA opens the native iPhone Camera app, scans the QR code from the console dashboard, and taps the prompt. The app installs directly onto their home screen in **10 seconds**!

### 2. Wireless ADB 1-Click Multi-Device Push (Instant Test Desk Sync) 📱⚡
- **Status:** **Implemented & Fully Operational** ✓
- **The Problem:** After an APK is built, QA or developers have to manually download it on each physical test device or plug in USB cables one by one.
- **The Solution:** The backend auto-detects all USB and Wi-Fi Android devices connected to the local development environment using standard `adb devices -l`.
- **Technical Mechanics:**
  - **Endpoints:**
    - `GET /api/deployment/adb/devices`: Returns active Android devices categorized as `usb`, `wireless`, or `emulator`, including model names and connection states.
    - `POST /api/deployment/adb/connect`: Pairs new wireless Android phones over local Wi-Fi via `adb connect <ip>:<port>`.
    - `POST /api/deployment/adb/disconnect`: Disconnects wireless devices via `adb disconnect <ip>:<port>`.
    - `POST /api/deployment/adb/push`: Dispatches parallel APK installs (`adb -s <serial> install -r <apk>`) across all selected devices using a thread pool.
  - **The Magic:** When an APK build finishes, click **Push to Devices (ADB)**. Instantly pushes and updates the build across 3–5 desk phones in parallel!

### 3. Two-Way ChatOps Bot (Slack / WhatsApp / Discord Remote Release) 💬🤖
- **Status:** **Implemented & Fully Operational** ✓
- **The Problem:** Engineering leads or release managers away from their desks need to trigger emergency builds or client previews and immediately access the resulting binaries.
- **The Solution:** Bidirectional webhook integration with Slack, Discord, and incoming webhooks supporting asynchronous callback dispatch.
- **Technical Mechanics:**
  - **Incoming Endpoints:** `POST /api/deployment/webhook/incoming/slack`, `POST /api/deployment/webhook/incoming/github`, `POST /api/deployment/webhook/incoming`.
  - **Asynchronous Execution:** Incoming Slack slash commands (`/deploy <app> <command>`) provide a transient `response_url`. The backend captures this URL in the job execution metadata.
  - **Rich Block Kit Callback:** Upon build completion, `notify_job_finished()` dispatches a rich Slack card to `response_url` with job status, duration, direct APK/IPA download buttons, and an inline QR scan URL.
  - **The Magic:** Trigger a build from Slack on your phone; when done, Slack notifies you with download links and install QR codes right in the thread!

### 4. Build Time Profiler & Compilation Bottleneck Heatmap 📊⏱️
- **Status:** **Implemented & Fully Operational** ✓
- **The Problem:** Builds suddenly become slow (jumping from 2 minutes to 12 minutes), but developers don't know which Gradle task, CocoaPod, or heavy uncompressed asset caused the lag.
- **The Solution:** Real-time log parsing engine that categorizes build phases and identifies compilation bottlenecks.
- **Technical Mechanics:**
  - **Endpoints:**
    - `GET /api/deployment/build-profile`: Analyzes the most recent completed job's terminal log.
    - `GET /api/deployment/job/profile?job_id=<id>`: Analyzes log output for any historical job execution.
  - **Phase Categorization:** Log lines are parsed into 6 primary mobile build phases:
    1. **Dependencies** (`flutter pub get`, Gradle resolution, CocoaPods)
    2. **Compilation** (Kotlin, Java, Swift, `dart_compile`)
    3. **Assets** (Asset bundling, font compilation, icon generation)
    4. **Linking** (Native library linking, C++ shared objects)
    5. **Packaging** (Dexing, resource shrinking, APK/IPA assembly)
    6. **Signing** (Keystore signing, Xcode code signing)
  - **Bottleneck Detection:** Any phase consuming **≥ 30%** of total build time is flagged as a bottleneck with actionable recommendations (e.g. enabling Gradle daemon caching, splitting large assets, or tuning Swift compilation flags).
  - **The Magic:** A visual segmented color bar and bottleneck cards pinpoint exactly what slowed down the build.

### 5. Smart Silent Cache Warmer (Zero Cold-Start Lag) 🔥
- **Status:** **Implemented & Fully Operational** ✓
- **The Problem:** Switching Git branches or pulling new commits triggers heavy dependency re-resolutions on the next build, adding 2–5 minutes of delay.
- **The Solution:** Low-priority background daemon that monitors Git branch switches and dependency lockfile changes, warming caches ahead of time.
- **Technical Mechanics:**
  - **Endpoints:**
    - `GET /api/deployment/cache-warmer/status`: Returns current cache state (`idle`, `warming`, `ready`, `error`), watched branch, and last warmed timestamp.
    - `POST /api/deployment/cache-warmer/warm`: Manually forces an immediate background dependency cache refresh.
  - **Intelligent Non-Blocking Execution:**
    - Tracks SHA-256 digests of `pubspec.yaml`, `pubspec.lock`, and `Podfile.lock`.
    - Periodically checks Git `HEAD` commit.
    - If a dependency change or branch switch occurs and **no builds are actively running**, silently executes `flutter pub get` in the background.
  - **The Magic:** When developers sit down and click "Build", dependencies are already 100% resolved and cached!

### 6. Zero-Friction Crash Symbol Vault (Auto-Upload dSYM & ProGuard Mappings) 🛡️
- **The Problem:** When release builds are obfuscated with R8/ProGuard on Android or stripped on iOS, production crash reports show illegible stack traces (`at com.a.b.c(Unknown Source)`). Uploading symbols manually is tedious and often forgotten.
- **The Solution:** The build pipeline automatically captures the generated `mapping.txt` and `.dSYM.zip` archives immediately after compilation.
- **The Magic:** Automatically uploads symbols to **Firebase Crashlytics** and **Sentry** during the build job. Every release has 100% human-readable crash logs on day one without extra developer steps!

### 7. Pre-Release Deep Link & Universal Link Validator 🔗
- **The Problem:** Release builds frequently break marketing campaigns or push notifications because Apple's `apple-app-site-association` (AASA) or Android's `assetlinks.json` domain fingerprints don't match the production keystore.
- **The Solution:** App Doctor queries the target domain's live `/.well-known/assetlinks.json` and AASA files, extracting the SHA256 fingerprints and team IDs.
- **The Magic:** Compares live web domain configurations against the keystores and certificates in your project. Warns on the dashboard *before* store upload if deep links will fail!

### 8. White-Label Multi-Client Batch Matrix (1-Click Build 5 Brands) 🎨🚀
- **The Problem:** Agencies and consultancies frequently maintain a single core codebase deployed for 3 to 10 different clients with different bundle IDs, app icons, splash screens, and colors. Compiling them one by one takes hours.
- **The Solution:** A batch matrix builder that reads client theme profiles from the workspace config.
- **The Magic:** Click **Build All Clients**. The console queues and orchestrates parallel builds for Client A, Client B, and Client C across local CPU and GitHub Actions, delivering all branded APKs and IPAs simultaneously.

### 9. 30-Second Headless Smoke Test & Visual Screenshot Proof 📸🤖
- **The Problem:** Developers ship a build that crashes on launch because of a missing runtime environment variable or asset file, only noticed 20 minutes later by QA.
- **The Solution:** A post-build headless smoke runner that boots a local simulator/emulator, launches the generated APK/IPA, navigates through the primary bottom navigation tabs, and takes 3 screenshots.
- **The Magic:** The dashboard displays a glowing green **"Launch Smoke Test: PASSED ✓"** badge with thumbnail screenshots before QA testers even download the APK!

### 10. Store Metadata & Localized Release Notes Previewer 📝🌍
- **The Problem:** Fastlane metadata contains changelogs in 12 different languages (`en-US`, `de-DE`, `fr-FR`, `es-ES`), but nobody knows if formatting or character limits broke until the Play Console rejects the upload.
- **The Solution:** A visual Store Listing Preview modal that renders exactly how the Google Play / App Store update card will look on phones in each language.
- **The Magic:** Flags character limits (e.g. 500 characters for Play Store release notes) and missing translations right inside the console before triggering store submission.




