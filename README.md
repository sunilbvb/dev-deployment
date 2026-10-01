# Dev Deployment Console 🚀

A lightweight, self-hosted web console to build, sign, upload and release mobile apps — Flutter first, with React Native, native and web projects supported — without typing terminal commands.

Open `http://localhost:18112`, pick a project tab, pick an app, choose an environment, click a command and watch the live log.

> **Backend:** `features/deployment/backend/` — Python standard library only
> **Frontend:** `features/deployment/frontend/` — vanilla HTML/JS using the [`developer-dashboard-ui`](https://github.com/sunilbvb/developer-dashboard-ui) kit
> **Build/release scripts:** `features/deployment/scripts/` — Bash + one Dart release tool
> **Default port:** `18112` (`DEPLOYMENT_PORT`)

---

## 📑 Table of Contents

1. [What It Does](#-what-it-does)
2. [Quick Start](#-quick-start)
3. [Projects: Import & Tabs](#-projects-import--tabs)
4. [How Apps and Packages Are Detected](#-how-apps-and-packages-are-detected)
5. [The Home Screen](#️-the-home-screen)
6. [Configure (Per-App Settings)](#️-configure-per-app-settings)
7. [Credentials: Play Keys, Apple .p8, Firebase](#-credentials-play-keys-apple-p8-firebase)
8. [Building & Uploading](#-building--uploading)
9. [Releases: Changelog, Git Tags & Push](#️-releases-changelog-git-tags--push)
10. [Safety & Security](#️-safety--security)
11. [Customizing Commands](#️-customizing-commands)
12. [CI/CD Webhook](#-cicd-webhook)
13. [Deployment History](#-deployment-history)
14. [Architecture & API](#️-architecture--api)
15. [Configuration & Data Files](#-configuration--data-files)
16. [Environment Variables](#-environment-variables)
17. [Known Limitations](#️-known-limitations)
18. [Contributing](#-contributing) · [FAQ](FAQ.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md) · [License](#-license)

---

## 💡 What It Does

- **Finds your apps automatically** in any layout: single app, several apps, apps + shared packages, with or without Melos, Dart pub workspaces.
- **One tab per project** on the home screen — several projects side by side, each browser tab independent.
- **One-click commands**: Build IPA / AAB / APK, Build & Upload to TestFlight / Google Play, Clean, Pub Get, and 12 release actions.
- **Live terminal** with every line streamed, plus a persistent **History** tab.
- **Credentials handled by the tool**: scan any folder for Play service-account keys, App Store Connect `.p8` keys and Firebase configs, import them in one click. Keys are stored outside your project (`chmod 600`) and passed to builds automatically.
- **Releases from git history**: changelog compiled from commits since the last tag, annotated tag, push — every git command and its result is shown in the log.
- **Safety gates**: production-upload confirmation, one job per app at a time, localhost-only server with an auth token.

The console never modifies your app code. It only writes its own settings into `<project>/.dev-dashboard/` and, for releases, `CHANGELOG.md` / `pubspec.yaml` version bumps plus git commits and tags.

---

## 🏁 Quick Start

### Prerequisites

| Tool | Needed for |
|---|---|
| **Python ≥ 3.10** | The console server (macOS ships 3.9 — install with `brew install python@3.12`) |
| **Bash** | Build / upload scripts |
| **Flutter SDK, Dart** | Flutter builds and the release tool |
| **Xcode + CocoaPods** (macOS) | iOS builds |
| **JDK 17 / Android SDK** | Android builds |
| **fastlane** (via rbenv/bundler) | Store uploads |
| **git** | Releases (uses your existing SSH keys / credential helper) |
| **Melos** | Only for Melos workspaces that define their own deploy scripts |

### Start

```bash
git clone -b develop https://github.com/sunilbvb/dev-deployment.git
cd dev-deployment
cp .env.example .env          # optional: set WORKSPACE_ROOT / DEPLOYMENT_PORT
./start.sh
```

If `python3` on your machine is older than 3.10, put a newer one first on `PATH`:

```bash
PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH" ./start.sh
```

Open `http://localhost:18112`. The page receives the API auth token automatically; the token itself is stored in `~/.config/dev-deployment/auth_token.txt`.

`WORKSPACE_ROOT` (in `.env` or the environment) only picks the project shown first. Every other project is added from the UI with **+ Import Project**.

### Background service

| Action | Command |
|---|---|
| Start in background | `./features/deployment/bin/start-deployment.sh` |
| Stop | `./features/deployment/bin/stop-deployment.sh` |
| Status | `./features/deployment/bin/status-deployment.sh` |
| Restart | `./features/deployment/bin/restart-deployment.sh` |

---

## 📂 Projects: Import & Tabs

### Import a project

1. Click **+ Import Project** (top right).
2. Click **Choose project folder…** — the native Finder dialog opens (Linux: `zenity`; systems without a dialog show a path field instead).
3. The dialog shows what was detected: folder name, **layout type**, the **apps** and the **packages**.
4. Click **Add project**. It appears as a new tab and opens.

Choosing a folder that is already added shows **Already added — open it** and simply opens its tab. A folder without any app shows a message and cannot be added.

### Project tabs

Every added project is a tab in the **Projects** bar. Clicking a tab shows that project — there is no separate "switch" step:

- The choice is **per browser tab**: two windows can show two different projects at the same time.
- Running builds keep running; a job's log, history entry and any chained release always belong to the project it was started from.
- **Remove a project**: hover its tab and click **×**. Only the tab is removed — the folder and its `.dev-dashboard/` settings stay, so importing it again restores everything. Projects with a running build cannot be removed; the startup project (`WORKSPACE_ROOT`) has no **×**.
- The list of added projects is stored in `config/workspaces_list.json` (local, not committed).

---

## 🔍 How Apps and Packages Are Detected

Detection runs on the chosen folder with no configuration.

| Folder layout | Shown as |
|---|---|
| One Flutter app at the root | **Single app** |
| One app at the root with local `packages/` | **Single app with local packages** |
| Several apps, no packages, no Melos | **Multiple apps (no packages, no Melos)** |
| Several apps plus shared packages, no Melos (any folder names, e.g. `mobile/`, `shared/`) | **Multiple apps with shared packages (no Melos)** |
| `melos.yaml` or `melos:` in the root `pubspec.yaml` | **Melos monorepo (apps + packages)** |
| `workspace:` list in the root `pubspec.yaml`, no Melos | **Dart pub workspace (apps + packages, no Melos)** |

**Rules**

- **Melos / pub workspace members** come from their `packages:` / `workspace:` lists; only folders with a `pubspec.yaml` or `package.json` count, and Melos `ignore:` patterns apply.
- **Otherwise** every folder with a `pubspec.yaml` or `package.json` up to 4 levels deep is a project. Inside a project, platform and source folders (`android/`, `ios/`, `lib/`, `test/`, `build/`, …) are never searched, but nested packages (e.g. `profile/profile_logic`) are found.
- Skipped everywhere: `example/`, `build/`, `.dart_tool/`, `node_modules/`, `Pods/`, hidden folders.
- **App vs package**: a Flutter project is an **app** if it has `android/`, `ios/` or an entry point `lib/main*.dart` (so `main_dev.dart` flavor entry points count). Flutter **plugins** (`flutter: plugin:`) and libraries are **packages**. Packages are listed under the app grid as *not deployable*.
- **App IDs are folder names** (`apps/pim` → `pim`); the display name comes from `pubspec.yaml`. Folder names are stable, so saved settings keep matching.
- Other stacks: `package.json` → React Native (with mobile folders) or Node; Gradle / Xcode projects without a manifest → native.

**Flavors** come from Android `productFlavors { … }` in `android/app/build.gradle(.kts)` (falling back to `android/app/src/<flavor>/`) and from iOS `ios/Flutter/*.xcconfig` names. Apps without flavors get no environment tabs and no `--flavor` flags.

Detected apps are cached in `<project>/.dev-dashboard/apps_config.json`. After moving apps around, use **Configure → Rescan Workspace**, or delete that file to regenerate it (custom names, colors and icons are not kept automatically).

---

## 🖥️ The Home Screen

| Area | What it does |
|---|---|
| **Header** | **Configure** opens per-app settings; **+ Import Project** adds a project. |
| **Projects bar** | One tab per added project. |
| **Select App** | Deployable apps as cards. *N packages (not deployable)* expands to the package list. |
| **Environment tabs** | Dev / QA / Prod / … — only for apps that have flavors. |
| **Commands** | Grouped into **iOS**, **Android**, **Combined Deploy**, **Release** and **Utilities**. Cards marked **LOCKED** need credentials (see below). |
| **Ready to execute** | The exact command that will run, with **Run** and **Stop**. |
| **Live Terminal** | Real-time output of the running job, including error output. If the server is unreachable it says so instead of showing an empty list. |
| **History** | Past jobs with status, duration, command and log excerpts; filter by app, flavor and status. |

---

## ⚙️ Configure (Per-App Settings)

**Configure** opens the setup dialog. Pick an app on the left, then a tab:

| Tab | Contents |
|---|---|
| **General** | Flavors (leave empty for a single app) and per-flavor iOS bundle IDs / Android package names. |
| **Keys** | **Find & Import Keys** — scan a folder for credentials (see next section). |
| **iOS** • | Apple ID, App Store Connect Issuer ID, `.p8` API key (drop file or click), certificate/profile status. |
| **Android** • | Google Play service-account key: status, **Choose JSON key…**, *Use for all apps*, **Remove**; optional manual path. |
| **Firebase** | `google-services.json` / `GoogleService-Info.plist` paths per flavor. |
| **Release** | Auto-run a release action after a successful deploy/upload. |

The dot on **iOS** / **Android** is green when upload credentials are configured and amber when they are missing. The tab you used last is remembered.

Buttons below every tab: **Auto-Scan App** and **Scan All Apps** (fill bundle IDs, package names, flavors and Firebase paths from the source), **Rescan Workspace** (re-detect apps), **Regenerate Commands**, **Save Config**.

Settings are saved to `<project>/.dev-dashboard/deploy_config.json`. That file holds identifiers and paths only — never key contents — so it is safe for teams that commit it.

---

## 🔑 Credentials: Play Keys, Apple .p8, Firebase

### Find & Import Keys

**Configure → Keys**

1. **Choose folder to scan…** (native dialog) or **Scan this workspace**.
2. Files are recognised **by their contents**, not by name:

   | Found | Recognised by |
   |---|---|
   | Google Play service account | JSON with `"type": "service_account"`, `private_key`, `client_email` |
   | App Store Connect API key | `.p8` with a private key, named `AuthKey_<KEYID>.p8` |
   | Other Apple keys | other `.p8` files (In-App Purchase / APNs) — listed but **not importable**, they cannot authenticate uploads |
   | Firebase Android | `google-services.json` structure; matched to apps/flavors by package name |
   | Firebase iOS | `GoogleService-Info.plist` with `BUNDLE_ID`; matched by bundle ID |

   Service accounts are ranked: names like *play*, *deploy*, *publish*, *github-actions*, *fastlane* are marked **likely Play uploader**; *firebase-adminsdk* / *revenuecat* are marked **likely Firebase / other service**. Only Google Play Console can confirm access, so pick the right one.
3. Click **Import** per result and choose **This app** or **All apps** (Firebase files: choose the flavor).

You can also upload directly: **Android → Choose JSON key…** for a Play key, **iOS → drop `AuthKey_XXXXXXXXXX.p8`** for an Apple key (Issuer ID is taken from the field above it).

### Where things are stored

| Item | Location |
|---|---|
| Imported Play keys | `~/.config/dev-deployment/keys/play-<project>-<hash>.json` (`chmod 600`) |
| Imported `.p8` keys | `~/.appstoreconnect/private_keys/AuthKey_<KEYID>.p8` (`chmod 600`, Apple's standard folder) |
| Which key belongs to which app | `~/.config/dev-deployment/credentials.json`, per project and app (`chmod 600`) |
| Firebase file paths | `<project>/.dev-dashboard/deploy_config.json` (they are not secrets) |

Nothing secret is written into the project. Each teammate imports their own keys. Older versions embedded `.p8` contents in `deploy_config.json`; on startup the server moves them to the private store and removes them from the file.

### How builds receive credentials

Every job gets these environment variables for its app (an app-specific key overrides one set for *All apps*):

| Variable | Used by |
|---|---|
| `SERVICE_ACCOUNT_JSON` | Google Play uploads (fastlane `supply`) |
| `APPLE_API_KEY`, `APPLE_API_ISSUER`, `APPLE_API_KEY_PATH` | iOS builds and TestFlight uploads |

**Play key lookup order** (first found wins): imported key → `play_service_account_path` typed in Configure → `<project>/private_keys/play-store-deployer.json` → `<app>/private_keys/play-store-deployer.json` → `<app>/android/play-store-deployer.json` → `~/.config/dev-deployment/play-store-deployer.json`.

**Apple key lookup order**: imported key → `APPLE_API_KEY` / `APPLE_API_ISSUER` in the app's `env/<flavor>.json` → `APPLE_API_KEY_BASE64` env var → `~/.appstoreconnect/private_keys/` → `~/.private_keys/` → `<project>/private_keys/`.

Existing setups keep working: the Configure status shows keys found in these fallback locations as *auto-detected* or *from app env file*.

### Upload commands are locked until credentials exist

**Build & Upload IPA**, **Upload IPA only** and **Build & Deploy Both** stay **LOCKED** until the app has an Apple ID, an imported key, or a key in its env file.

---

## 📦 Building & Uploading

1. Click the project tab and the app.
2. Choose the environment tab (if the app has flavors).
3. Click a command card, check the command under **Ready to execute**, click **Run**.
4. Production store uploads ask for confirmation first.
5. **Stop** ends the running job (process group `SIGTERM`, then `SIGKILL`).

| Command | What runs |
|---|---|
| Build IPA / Build IPA for Device | Xcode archive + IPA export (App Store or development signing) |
| Build & Upload IPA / Upload IPA only | IPA to TestFlight via fastlane |
| Build AAB / Build APK | `flutter build appbundle` / `flutter build apk --release` |
| Build & Upload AAB / Upload AAB only | AAB to the Play Store **internal testing** track via fastlane |
| Build & Deploy Both | iOS + Android with one shared version bump |
| Clean Project / Pub Get | `flutter clean` / `flutter pub get` in the app folder |

**How scripts find things** (works for any layout):

- **App folder** — resolved by the backend (`resolveAppDir`), wherever the app lives.
- **Android package name** — saved `android_id_<flavor>` in Configure, else read from the app's Gradle files (`applicationId`, per flavor).
- **Env file** — `<app>/env/<flavor>.json` (single apps: `env/default.json`, `env.json`).

**Melos workspaces**: if the root `pubspec.yaml` defines a matching Melos script (e.g. `<app>:deploy:<env>:aab:raw`, as in TYRIOS), it is run with `melos run`. If not, the console runs the same build/upload step directly with Flutter in the app folder and says so in the log (`Melos script '…' not defined; running … directly`). No Melos scripts need to be written.

---

## 🏷️ Releases: Changelog, Git Tags & Push

The **Release** commands run `features/deployment/scripts/release_changelog_tagger.dart` through `run_build.sh`. They use your normal `git` and your existing credentials, and push to the repository's `origin` remote. Apps that are their own git repository (e.g. `apps/gyo` with its own remote) are released inside that repository.

### The release summary is generated for you

Commits since the app's previous tag are grouped by [Conventional Commit](https://www.conventionalcommits.org) type:

```text
## [1.0.2+3] - 2026-10-01
_1 feature · 1 fix_
**👥 Contributors:** Sunil (2)

### 🚀 Features
* **customer**: wishlist (`91ae6b6`, 2026-10-01 18:58, Sunil)

### 🐛 Bug Fixes
* **customer**: crash on empty cart (`e994f6d`, …)
```

The same text is used as the **annotated tag message**, the **release commit body** and the app's **`CHANGELOG.md`**. Only commits touching the app (or its internal dependencies) are included. Write commits as `feat(scope): …`, `fix: …` to get useful notes.

Tags are named `<app>-v<version>` from `pubspec.yaml`, e.g. `customer-v1.0.2+3`.

### Release actions

| Action | Files | Commit | Tag | Push |
|---|---|---|---|---|
| 1. Preview Changelog (Dry-run) | – | – | – | – |
| 2. Update CHANGELOG.md Only | ✔ | – | – | – |
| 3. Update Changelog & Git Commit | ✔ | ✔ | – | – |
| 4. Changelog + Commit + Local Git Tag | ✔ | ✔ | ✔ | – |
| 5. Full Release (Tag & Push to Remote) | ✔ | ✔ | ✔ | ✔ |
| 6–8. Bump Patch / Minor / Major & Release | version bump + ✔ | ✔ | ✔ | – |
| 9. Store "What's New" Release Notes | – | – | – | – |
| 10. Pre-Flight Verify & Full Release | analyze/test first, then as 5 | ✔ | ✔ | ✔ |
| 11. Monorepo Unreleased Report | lists unreleased commits for every app/package | | | |
| 12. Rollback / Delete Release Tag | deletes the local tag | | | |

**Recommended flow**: **1. Preview** → **6/7/8 Bump** (or **4** without bumping) → **5. Full Release**. When the tag already exists locally on the current commit but not on the remote, Full Release just pushes it.

### What the log shows

```text
🔎 Commits in release window (customer-v1.0.1+2 ➔ HEAD): 2
   · b6301d9  fix(api_client): timeout  (skipped: belongs to api_client)
   ✔ 91ae6b6  feat(customer): wishlist  [app]
   → 1 included, 1 skipped
   $ git commit --cleanup=verbatim -F '<message: "chore(release): release customer-v1.0.2+3" + 9 more lines>'
     │ [main 2bbc0bf] chore(release): release customer-v1.0.2+3
     └ ok
   $ git push origin customer-v1.0.2+3
     │  * [new tag]   customer-v1.0.2+3 -> customer-v1.0.2+3
     └ ok
══════════════════ RELEASE SUMMARY ══════════════════
   Tag:        customer-v1.0.2+3
   Commit:     2bbc0bf
   Branch:     main
   Remote:     git@github.com:org/repo.git
   Pushed:     yes
```

Every git command that changes the repository (`add`, `commit`, `tag`, `push`) is printed with its output. A failed push marks the job **failed**, shows git's error and leaves the release local so it can be pushed again.

### Rules

- The project must be a git repository; Full Release needs an `origin` remote.
- Commit, tag and push are only allowed on `main`, `master`, `develop`, `release`, `release/*`, `hotfix/*` (Preview and changelog-only work on any branch).
- The previous release tag must be part of the current branch's history.
- An existing tag is never overwritten; bump the version first.

---

## 🛡️ Safety & Security

- **Localhost only.** The server rejects non-localhost `Host` headers (DNS rebinding) and foreign `Origin`s. Do not expose the port (no `0.0.0.0`, no ngrok).
- **Auth token.** Every `/api/*` call needs `X-API-Token`; the page gets it injected, scripts read `~/.config/dev-deployment/auth_token.txt`.
- **Production gate.** Store uploads for production ask for confirmation (`confirmed: true` in the API).
- **One job per app.** A second job for a busy app is rejected with `APP_BUSY`; locks are per project.
- **Only configured commands run.** `/execute` resolves the command from templates; arbitrary commands cannot be posted.
- **Folder access.** The server only reads projects that were added, plus folders you just chose in the native dialog.
- **Secrets** stay outside projects (see Credentials). Request bodies are limited to 1 MB.

---

## ⚙️ Customizing Commands

Commands come from [`config/deployment_templates.json`](config/deployment_templates.json), grouped by `ios`, `android`, `combined`, `release`, `utility`.

```json
{
  "id": "build_web",
  "name": "Build Web App",
  "description": "Compile production web bundle",
  "runner": "direct",
  "command_template": "flutter build web --release",
  "icon": "globe",
  "color": "#3b82f6"
}
```

| Placeholder | Replaced with |
|---|---|
| `{flavor}` | Selected environment (removed for apps without flavors) |
| `{app_id}` | App ID (folder name) |
| `{bundle_id}`, `{android_package}`, `{apple_id}` | Values from Configure |

`"runner": "direct"` commands run in the app folder. Templates whose ID is implemented in `run_build.sh` (build/upload/deploy and all release actions) run through the script layer; everything else always runs directly.

---

## 🌐 CI/CD Webhook

Set `WEBHOOK_SECRET` in `.env`, then:

```bash
curl -X POST http://localhost:18112/api/deployment/webhook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"app":"customer","templateId":"build_aab","flavor":"prod","confirmed":true}'
```

GitHub-style `X-Hub-Signature-256` (HMAC-SHA256 of the body) is accepted instead of `X-Webhook-Secret`. Without `WEBHOOK_SECRET` the endpoint is disabled (`503`). The server is localhost-only, so the caller must run on the same machine (e.g. a self-hosted runner).

---

## 📋 Deployment History

Each finished job is appended to `<project>/.dev-dashboard/deployment_history.jsonl` with `id`, `app`, `templateId`, `flavor`, `env`, `command`, `status`, `returnCode`, `startedAt`, `finishedAt`, `durationSeconds`, `outputExcerpt`, `errorExcerpt` and `chainedJobId`. The **History** tab reads it.

---

## 🏗️ Architecture & API

- **How it works, design rules and every file:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **REST API** (all endpoints, headers, request/response shapes): [docs/API.md](docs/API.md)
- **Why it is built this way:** [docs/adr/](docs/adr/)

---

## 📁 Configuration & Data Files

| File | Scope | Contents |
|---|---|---|
| `config/deployment_templates.json` | tool | Command definitions |
| `config/workspaces_list.json` | local | Added projects `[{name, path}]` |
| `.env` | local | Environment overrides |
| `<project>/.dev-dashboard/apps_config.json` | project | Detected apps: id, name, path, stack, `is_package`, color, icon |
| `<project>/.dev-dashboard/deploy_config.json` | project | Flavors, bundle IDs, package names, Apple ID, issuer, Firebase paths, auto-release |
| `<project>/.dev-dashboard/deployment_history.jsonl` | project | Job history |
| `~/.config/dev-deployment/auth_token.txt` | user | API token |
| `~/.config/dev-deployment/credentials.json` | user | Key ↔ app mapping |
| `~/.config/dev-deployment/keys/` | user | Imported Play keys |
| `~/.appstoreconnect/private_keys/` | user | Imported `.p8` keys |

The console adds `.dev-dashboard/` to the project's `.gitignore` when it first writes settings, unless the `.gitignore` already mentions it. If your team commits these files, `deploy_config.json` contains no secrets.

```json
{
  "apps": {
    "customer": {
      "flavors": ["dev", "prod"],
      "bundle_id_prod": "com.acme.customer",
      "android_package_prod": "com.acme.customer",
      "apple_id": "developer@acme.com",
      "apple_issuer_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "google_services_json_prod": "mobile/customer/android/app/src/prod/google-services.json",
      "auto_release_on_success": false,
      "auto_release_action": "release_push",
      "auto_release_flavors": ["prod"]
    }
  }
}
```

---

## 🔧 Environment Variables

| Variable | Purpose |
|---|---|
| `WORKSPACE_ROOT` | Project shown first (default: `config/active_workspace.txt`, else this repo) |
| `DEPLOYMENT_PORT` | Server port (default `18112`) |
| `DEPLOYMENT_AUTH_TOKEN` | Fixed API token instead of the generated one |
| `DEPLOYMENT_TMP_DIR` | Temp/log directory for jobs |
| `WEBHOOK_SECRET` | Enables `/api/deployment/webhook` |
| `GOOGLE_CHAT_WEBHOOK_URL` | Build notification cards in Google Chat |
| `DEFAULT_TEAM_ID` | Apple team fallback |

Set by the console for every job: `WORKSPACE_ROOT`, `DEPLOYMENT_PYTHON`, `DASHBOARD_SCRIPTS_PATH`, and the credential variables listed above.

---

## ⚠️ Known Limitations

- **Dynamic Gradle flavors** (generated in loops or remote scripts) cannot be read statically — enter them in Configure → General.
- **iOS builds need macOS** with Xcode.
- **Single machine**: the server is localhost-only by design.
- **Release summaries are generated, not edited** — adjust commit messages, or edit `CHANGELOG.md` after **2. Update CHANGELOG.md Only**.

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests and the roadmap, and [docs/proposals/](docs/proposals/) for features that are designed and ready to build. More answers in [FAQ.md](FAQ.md); how the code is organised is in [ARCHITECTURE.md](ARCHITECTURE.md). Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## 📄 License

[MIT](LICENSE)
