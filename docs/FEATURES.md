# Complete Features Catalog ⚡

An exhaustive guide to all capabilities available in the Dev Deployment Console.

---

## 🧭 Core Dashboard & Workspaces
- **Multi-Workspace Switcher**: Import and jump between independent project directories with instant configuration isolation.
- **Melos Monorepo Auto-Discovery**: Automatically identifies sub-packages, deployable apps, and shared libraries.
- **Dynamic Command Tiles**: Context-aware build tiles grouped into **Dev**, **QA**, and **Prod** environments.
- **Production Guard Modal**: Safeguards against accidental production deployments with interactive verification confirmation.
- **Live Output Streaming**: Subprocess execution with real-time stdout/stderr log output, elapsed stopwatch timer, and process termination (`SIGTERM`/`SIGKILL`).

---

## 🔍 Pre-flight Diagnostics (App Doctor)
- **1-Click System Check**: Evaluates 12+ environment prerequisites in under 2 seconds.
- **SDK Inspections**: Verifies Flutter SDK, Dart runtime, Android SDK, and CocoaPods paths and versions.
- **Signing Keystore Check**: Validates release keystore presence, alias, and certificate expiry.
- **Git Hygiene**: Alerts developers if dirty working trees or uncommitted code are about to be packaged.
- **Firebase Validation**: Ensures cross-platform project IDs (`google-services.json` and `GoogleService-Info.plist`) match the intended environment.

---

## 📦 Binary Packaging, Size & Distribution
- **Local APK Server & QR Code**: Instantly streams compiled `.apk` binaries over local Wi-Fi with pure-Python Reed-Solomon QR codes.
- **iOS OTA IPA Hosting**: Dynamically generates Apple XML `manifest.plist` enabling wireless installation via iPhone camera QR scan.
- **Build Size Inspector & Diff**: Inspects ZIP central directory structures without disk extraction, alerting to uncompressed assets (`ZIP_STORED` ≥ 500 KB) and size regressions.
- **Certificate & Keystore Sentinel**: Proactively checks Apple `.p8` keys and Android keystores, warning on certificates expiring within 30 days.

---

## 📱 Mobile Innovations
- **Wireless ADB Manager**: Discovers connected USB/Wi-Fi devices and emulators, pairs over Wi-Fi (`adb connect`), and installs APKs in parallel.
- **Build Time Profiler**: Parses compile logs into 6 distinct mobile phases, surfacing compilation bottlenecks with visual heatmaps.
- **Smart Silent Cache Warmer**: Monitors lockfile and Git branch changes, running background `flutter pub get` during idle moments.
- **GitHub Actions Hybrid Cloud**: Connects local builds to GitHub Actions cloud runners with automated starter workflow generation.

---

## 🔀 Automation & Universal Webhooks
- **Saved Pipelines**: Chains multi-step sequences (`Doctor` → `Build` → `Diff` → `Upload` → `Notify`) with fail-fast safety.
- **Outgoing Team Alerts**: Sends rich notification cards to Slack, Discord, Microsoft Teams, Google Chat, and WhatsApp.
- **Universal Inbound Webhooks**: Headless CI/CD ingestion verified via SHA-256 HMAC (`X-Hub-Signature-256`) and Slack signatures.
- **In-App Documentation Hub**: Built-in markdown documentation viewer with offline fallback and real-time endpoint search.
