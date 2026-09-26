# Contributing to Dev Deployment Console 🚀

Thank you for your interest in contributing to **Dev Deployment Console**! We welcome contributions from developers of all skill levels. Whether you are fixing a bug, adding a new feature, improving documentation, or refining UI components, your help is greatly appreciated.

---

## 📑 Table of Contents

1. [How to Get Started](#-how-to-get-started)
2. [Project Architecture Overview](#-project-architecture-overview)
3. [🚀 Open-Source Roadmap & Wishlist (Help Needed!)](#-open-source-roadmap--wishlist-help-needed)
4. [Development Setup](#-development-setup)
5. [Pull Request (PR) Guidelines](#-pull-request-pr-guidelines)
6. [Code Style & Standards](#-code-style--standards)

---

## 🏁 How to Get Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/dev-deployment.git
   cd dev-deployment
   ```
3. Check the **Roadmap & Wishlist** section below for ideas or open an issue to discuss a bug/feature before starting work.

---

## 🏗️ Project Architecture Overview

Dev Deployment Console is designed to be lightweight, zero-dependency (uses Python's standard library), and platform-agnostic:

- **Backend:** Python 3.11+ HTTP server (`features/deployment/backend/server.py` & `router.py`). No heavy frameworks (Flask/FastAPI/Django) — pure stdlib (`http.server`, `email.parser`, `subprocess`, `json`).
- **Frontend:** Vanilla HTML5, CSS3, and JavaScript (`features/deployment/frontend/`). Uses developer-dashboard-ui component kit (`.ui-card`, `.ui-field`, `.ui-dropzone`, etc.).
- **Build Engine:** Modular Bash scripts (`features/deployment/scripts/`) handling iOS, Android, Git, and Webhook tasks.

---

## 🚀 Open-Source Roadmap & Wishlist (Help Needed!)

We have identified several high-value features and improvements that would make great open-source contributions. Feel free to pick any item below!

### 📂 1. Open Project Folder Picker & Monorepo Inspection (Completed ✅)
- [x] **Folder Picker Button:** Browse directories visually using `<input type="file" webkitdirectory>`.
- [x] **Live Workspace Inspector (`/api/deployment/inspect-path`):** Inspect any folder path before switching — auto-detects app count, monorepo state, and tech stacks (Flutter, Node, Android, iOS).

### 🧠 2. Workspace & Melos Intelligence Roadmap (Help Needed!)

We aim to make Dev Deployment Console intelligent enough to seamlessly handle any project layout without manual configuration:

| Scenario / Capability | Current Status | What Needs to be Done (Wishlist Item) |
|---|---|---|
| **1. Single Flutter Project** | ✅ Fully Supported | Auto-detects `pubspec.yaml` in root and scans xcconfig / gradle. |
| **2. Multi-App Workspace (No Melos)** | ⚠️ Basic Support | Scans `apps/` subfolders, but treats all subfolders equally without distinguishing libraries. |
| **3. Monorepo (Apps + Packages)** | ⚠️ Needs Package Filter | Scans `apps/` and `packages/`. **Need logic** to separate deployable apps (`apps/*`) from internal library packages (`packages/*` with `publish_to: none` or no `android/`/`ios/` dirs). |
| **4. Auto-Root & Package Hierarchy** | 🟡 Basic | **Need Melos manifest parser** to read `melos.yaml` or `pubspec.yaml` (`melos:` key) to automatically resolve custom package location glob patterns (`packages: ["modules/*", "features/*"]`). |
| **5. Multiple Workspaces & Monorepos** | ✅ Fully Supported | `set_active_workspace()` handles dynamic switching between single apps and monorepos via UI/API without server restart. |
| **6. Melos Detection (`melos.yaml` vs `pubspec.yaml`)** | 🟡 Command engine checked; Discovery engine missing | `get_commands()` checks `melos.yaml` and `pubspec.yaml` (`melos:` key). **Need `discover_workspace_config()`** to use Melos config to drive app & package discovery. |
| **7. Multi-App Workspace (With Melos)** | 🟡 Partially Supported | Commands & scripts use Melos. **Need Task 2.2** to read custom Melos package patterns and Task 2.3 for bulk auto-scanning all Melos apps at once. |

#### Detailed Tasks to Implement:

- [x] **Task 2.1 — Smart Package Filter (Completed ✅):** `_detect_app_in_dir()` now checks `publish_to: none` and native `android/`/`ios/` directories to tag pure library packages (`is_package: true`), rendering a `PKG` badge in the UI.
- [ ] **Task 2.2 — Deep Melos Config Parser:** Add a `_parse_melos_config()` helper in `router.py` that reads `melos.yaml` or the `melos:` section inside `pubspec.yaml`. Extract the configured `packages:` glob paths (e.g. `apps/*`, `packages/*`, `services/*`) dynamically instead of hardcoding folder names.
- [ ] **Task 2.3 — Bulk Workspace Auto-Scan ("Scan All"):** Add a backend endpoint `POST /api/deployment/scan-all` and a UI button **"Scan All Apps"** to auto-discover and save Bundle IDs, Android Package names, and Firebase configs for all apps in a workspace at once.
- [ ] **Task 2.4 — Custom Flavor Auto-Detection:** Update `_scan_xcconfig_bundle_ids()` and `_scan_android_app_ids()` to read custom flavor names defined in `melos.yaml` scripts or Gradle `productFlavors { ... }` blocks (e.g. `staging`, `uat`, `sandbox`).

### 📱 3. Smarter iOS & Android Credential Scanning
- [ ] **iOS `GoogleService-Info.plist` Detection:** Auto-scan `ios/**/GoogleService-Info.plist` per flavor directory (`/dev/`, `/qa/`, `/prod/`) and auto-populate paths.
- [ ] **Support Staging / Custom Flavors in Scanner:** Expand `_scan_xcconfig_bundle_ids()` and `_scan_android_app_ids()` flavor maps to recognize `staging`, `uat`, `sandbox`, and `beta`.
- [ ] **Native Gradle `productFlavors` Parser:** Improve `build.gradle` parsing to read nested `productFlavors { ... }` blocks and extract exact per-flavor `applicationId` strings.

### 🎨 3. UI/UX Enhancements
- [ ] **Dark / Light Theme Toggle Persistence:** Add a clean toggle switch in the UI header and save user preference to `localStorage`.
- [ ] **Build Time Analytics:** Add a simple visual chart in the History tab showing build duration trends per app.
- [ ] **Custom Terminal Font Size / Clear Search:** Add a quick search bar inside the live terminal log viewer to filter build output lines in real-time.

### 🔔 4. Notification Integrations
- [ ] **Slack Webhook Support:** Expand notification engine beyond Google Chat to format and post rich Slack message blocks.
- [ ] **Discord Webhook Support:** Add Discord rich embed card formatting for build success/failure alerts.
- [ ] **Teams Webhook Support:** Add Microsoft Teams Adaptive Card templates for build reports.

---

## 🛠️ Development Setup

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
2. Start the development server:
   ```bash
   ./start.sh
   ```
3. Open `http://localhost:18112` in your browser.
4. Modify Python backend files or Frontend assets — the server picks up HTML/JS/CSS changes instantly on page refresh.

---

## 📤 Pull Request (PR) Guidelines

1. **Create a feature branch:**
   ```bash
   git checkout -b feat/melos-package-filter
   ```
2. **Commit with conventional commit messages:**
   - `feat(scan): filter non-deployable library packages in monorepos`
   - `fix(p8): resolve key path fallback when base64 is missing`
   - `docs(readme): update API reference table`
3. **Verify Python code syntax:**
   ```bash
   python3 -c "import ast; ast.parse(open('features/deployment/backend/router.py').read())"
   ```
4. **Push to your fork and submit a Pull Request!**

---

## 📄 License
By contributing to Dev Deployment Console, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
