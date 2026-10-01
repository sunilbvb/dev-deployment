# Frequently Asked Questions (FAQ) 📖

Answers to common questions about setup, projects, credentials, building, releasing and troubleshooting. The full guide is the [README](README.md); how the code is organised is in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📑 Table of Contents

1. [Getting Started](#1-getting-started)
2. [Projects & Detection](#2-projects--detection)
3. [Configuration](#3-configuration)
4. [Credentials](#4-credentials)
5. [Building & Uploading](#5-building--uploading)
6. [Releases & Git](#6-releases--git)
7. [Security](#7-security)
8. [Troubleshooting](#8-troubleshooting)
9. [Known Limitations](#9-known-limitations)

---

## 1. Getting Started

### What is this tool, and who is it for?
A local web console for mobile developers — Flutter first — to build, sign, upload (TestFlight / Google Play) and release apps with buttons instead of terminal commands, for any project layout.

### What do I need installed?
Python ≥ 3.10 (standard library only), Bash, and your normal build tools: Flutter/Dart, Xcode + CocoaPods (macOS, for iOS), JDK 17 + Android SDK, fastlane, git. See [Prerequisites](README.md#-quick-start).

### macOS says `Python 3.10 or higher is required`.
macOS ships Python 3.9. Install a newer one (`brew install python@3.12`) and start with it first on `PATH`:
```bash
PATH="/opt/homebrew/opt/python@3.12/libexec/bin:$PATH" ./start.sh
```

### How do I start and stop it? Where is the auth token?
`./start.sh` (foreground) or `./features/deployment/bin/start-deployment.sh` / `stop-deployment.sh` (background). The token is generated on first run and saved in `~/.config/dev-deployment/auth_token.txt`; the web page receives it automatically. Custom API calls need the `X-API-Token` header.

---

## 2. Projects & Detection

### How do I add a project?
**+ Import Project → Choose project folder…** opens the native folder dialog. The dialog then shows the detected layout, apps and packages; **Add project** adds it as a tab on the home screen and opens it.

### Do I need to "switch" projects?
No. Every added project is a tab; clicking a tab shows it. The choice is per browser tab, so two windows can show two projects at once, and running builds are not affected.

### How do I remove a project?
Hover its tab and click **×**. Only the tab goes away; the folder and its settings are kept, so **+ Import Project** brings it back with everything intact. A project with a running build cannot be removed, and the startup project (`WORKSPACE_ROOT`) always stays.

### Which folder layouts are supported?
All of these, with no configuration:

| Layout | Detected as |
|---|---|
| One Flutter app | Single app |
| One app + local `packages/` | Single app with local packages |
| Several apps, no packages, no Melos | Multiple apps (no packages, no Melos) |
| Several apps + shared packages, no Melos | Multiple apps with shared packages (no Melos) |
| Apps + packages with Melos | Melos monorepo (apps + packages) |
| Apps + packages with a Dart pub `workspace:` | Dart pub workspace (apps + packages, no Melos) |

Folder names do not matter (`apps/`, `mobile/`, `shared/`, …).

### How does it tell apps from packages?
A Flutter project with `android/`, `ios/` or `lib/main*.dart` is an app. Plugins (`flutter: plugin:` in `pubspec.yaml`) and libraries are packages — listed under the app grid as *not deployable* and excluded from deploy commands. `example/` apps inside packages are ignored.

### Why are my app IDs folder names instead of package names?
Folder names (`apps/pim` → `pim`) rarely change, so saved settings, commands and history keep matching. The display name still comes from `pubspec.yaml` and can be changed in Configure.

### My projects aren't detected.
Each project needs a `pubspec.yaml` (or `package.json`) and must be at most 4 folders deep (Melos/pub workspace members are found at any depth through their lists). Hidden folders and `build/`, `.dart_tool/`, `node_modules/`, `Pods/`, `example/` are skipped. Then use **Configure → Rescan Workspace**.

### The app list is outdated after I moved apps.
Apps are cached in `<project>/.dev-dashboard/apps_config.json`. Use **Rescan Workspace**, or rename that file to `apps_config.json.bak` to regenerate it on the next load.

---

## 3. Configuration

### Where are the settings?
In **Configure**, per app, on six tabs: General, Keys, iOS, Android, Firebase, Release. The dots on iOS/Android show whether upload credentials are set (green) or missing (amber).

### What is detected automatically?
Bundle IDs, Android package names (`applicationId` per flavor), flavors (`productFlavors`, xcconfig names) and Firebase config files. Use **Auto-Scan App** / **Scan All Apps** to fill them in.

### What do I enter by hand?
Only the Apple ID (if you use it) and, if not found, the App Store Connect Issuer ID. Keys are imported, not typed — see [Credentials](#4-credentials).

### Where is everything stored? Can I commit it?
`<project>/.dev-dashboard/` holds `apps_config.json`, `deploy_config.json` and `deployment_history.jsonl`. They contain identifiers and paths only — no key contents — so committing them is safe if your team wants shared settings. Keys and the key-to-app mapping live in your home folder.

### I changed my bundle ID. Why does the console still show the old one?
Auto-scan fills empty fields and does not overwrite your edits. Change the field in Configure → General, or clear it and run **Auto-Scan App** again.

---

## 4. Credentials

### Can the tool find my keys for me?
Yes. **Configure → Keys → Choose folder to scan…** (or **Scan this workspace**) finds Google Play service-account JSON files, App Store Connect `AuthKey_<KEYID>.p8` keys and Firebase configs by their **contents**, even with random file names. Click **Import** and choose *This app* or *All apps*.

### Several service accounts were found. Which one is the Play key?
Service-account files look identical. The scan marks names containing *play / deploy / publish / github-actions / fastlane* as **likely Play uploader** and *firebase-adminsdk / revenuecat* as **likely Firebase / other service**. Only Google Play Console (Users and permissions) can confirm which account has release access.

### Why can't I import `SubscriptionKey_….p8`?
In-App Purchase and APNs keys are also `.p8` files, but they cannot authenticate uploads. Only `AuthKey_<KEYID>.p8` (App Store Connect API key) can be imported.

### Where do imported keys go? Are they safe?
Play keys: `~/.config/dev-deployment/keys/` · `.p8` keys: `~/.appstoreconnect/private_keys/` · mapping: `~/.config/dev-deployment/credentials.json`. All `chmod 600`, outside your project, never committed. Each teammate imports their own.

### How do builds get the keys?
Each job receives `SERVICE_ACCOUNT_JSON`, `APPLE_API_KEY`, `APPLE_API_ISSUER` and `APPLE_API_KEY_PATH` for its app. A key imported for one app overrides one imported for *All apps*.

### I already have `private_keys/play-store-deployer.json` and `env/<flavor>.json` with `APPLE_API_KEY`. Do I have to import?
No. Those are still used as fallbacks; Configure shows them as *auto-detected* / *from app env file*. Importing is only needed for keys stored elsewhere. The full lookup order is in the [README](README.md#how-builds-receive-credentials).

### Why are iOS upload buttons LOCKED?
Upload IPA / Build & Upload IPA / Build & Deploy Both need an Apple ID, an imported `.p8` key, or `APPLE_API_KEY` in the app's env file.

---

## 5. Building & Uploading

### How do I build or upload?
Click the project tab → app → environment tab (if the app has flavors) → a command card → **Run**. The exact command is shown under *Ready to execute*; output streams into the **Live Terminal**.

### Which Play Store track is used?
Build & Upload AAB / Upload AAB only publish to **internal testing**.

### Does it work in a Melos workspace without Melos scripts?
Yes. If the root `pubspec.yaml` has a matching Melos script (e.g. `gyo_business:deploy:qa:aab:raw`) it runs with `melos run`; otherwise the same step runs directly with Flutter in the app folder, and the log says so.

### Why do I get a confirmation popup?
Production store uploads always ask for confirmation to prevent accidental releases.

### Why is my second job blocked (`APP_BUSY`)?
One job per app at a time; another app (or the same app in another project) can run in parallel.

### How do I stop a build?
Click **Stop**. The whole process group is terminated and the app lock is released.

### Where are logs and history?
Live output in the **Live Terminal** (including error output); finished jobs in the **History** tab and in `<project>/.dev-dashboard/deployment_history.jsonl`.

---

## 6. Releases & Git

### Does the tool need to be "connected" to git?
No. It runs your normal `git` with your existing SSH keys / credential helper and pushes to the repository's `origin` remote. Apps that are their own repository are released inside that repository.

### Where does the release summary come from?
It is generated from the commits since the app's last tag, grouped by Conventional Commit type (`feat:` → Features, `fix:` → Bug Fixes, others → maintenance) with contributors. The same text becomes the annotated tag message, the release commit and `CHANGELOG.md`. Run **1. Preview Changelog** to see it before anything is written.

### What is the recommended release flow?
**1. Preview** → **6/7/8 Bump Patch/Minor/Major** (creates the release locally) → **5. Full Release** (pushes it). Use **4. Local Git Tag** if the version in `pubspec.yaml` is already correct.

### What does the release log show?
The list of commits in the release window (✔ included / · skipped with the reason), every git command that changes the repository with its output (`$ git commit …`, `$ git tag …`, `$ git push …`), and a final **Release Summary** (tag, commit, branch, remote, pushed yes/no).

### Full Release says "RELEASE COLLISION ERROR: Tag already exists".
That version was already released. Bump the version first (6/7/8). If you just created the tag locally with a bump, Full Release pushes it instead of erroring.

### The push failed — what now?
The job is marked failed, git's error is shown, and the commit and tag stay local. Fix the cause (remote URL, access rights, network) and run **5. Full Release** again; it pushes the existing release.

### Why is tagging refused on my branch?
Commit/tag/push are allowed only on `main`, `master`, `develop`, `release`, `release/*`, `hotfix/*`. Preview and changelog-only work everywhere.

### Can I edit the summary before tagging?
Not in the UI yet. Improve commit messages, or run **2. Update CHANGELOG.md Only**, edit the file, then commit and tag.

---

## 7. Security

### Can I expose it on my network or through ngrok?
No. It is built for `localhost` only: non-localhost `Host` headers and foreign origins are rejected, every API call needs the token, only commands from the templates can run, and folder access is limited to added projects and folders you choose in the native dialog. Exposing it would allow remote command execution.

### How does the webhook work?
Set `WEBHOOK_SECRET`; requests to `/api/deployment/webhook` must carry `X-Webhook-Secret` or a GitHub `X-Hub-Signature-256` HMAC. Without the secret the endpoint is disabled.

---

## 8. Troubleshooting

### The page shows "Could not load commands".
The console server is not running or was restarted. Start it (`./start.sh`) and reload the page.

### My build fails with `--flavor dev`, but I have no flavors.
Flavors were typed in Configure → General for a project without Gradle/Xcode flavors. Clear the field and save.

### Android upload fails with "package_name must be provided".
The package name could not be found. Check `applicationId` in `android/app/build.gradle(.kts)` or set the Android package name for the flavor in Configure → General.

### "Service account file not found".
No Play key was found in any lookup location. Import one in Configure → Keys or Android, or place it at `<project>/private_keys/play-store-deployer.json`.

### My packages show build buttons.
They are probably cached from an older version. Run **Configure → Rescan Workspace**, or regenerate `apps_config.json`.

---

## 9. Known Limitations

- **Dynamic Gradle flavors** (generated in loops or remote scripts) cannot be detected statically — enter them in Configure → General.
- **iOS builds require macOS** with Xcode.
- **Localhost only** — no multi-user remote setup.
- **Release summaries cannot be edited in the UI** before tagging.
