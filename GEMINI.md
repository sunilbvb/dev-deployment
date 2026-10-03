# Dev Deployment Console — Project Guidelines & Standards

## Code Architecture & Modular Structure Standards (Mandatory)
Always structure and organize codebase files according to clean industry and modular standards:

### 1. Backend (Python ≥ 3.10)
- **Zero External Dependencies**: Built 100% on the Python standard library. Never add `pip install` requirements.
- **Minimal Root Directory**: The root `features/deployment/backend/` must only hold core servers and coordinators (`server.py`, `router.py`, `jobs.py`).
- **Domain Sub-Packages**: All functional domains must be organized in dedicated sub-packages with an `__init__.py`:
  - `automation/`: Device discovery, compilation profiling, cache warming, cloud CI.
  - `artifacts/`: APK, AAB, and IPA binary scanning, downloading, and Apple OTA manifest generation.
  - `notifications/`: Multi-provider webhooks and two-way ChatOps.
  - `build_size/`: In-memory ZIP central directory diffing and uncompressed asset detection.
  - `doctor/`: Pre-flight diagnostics and SDK/keystore checks.
  - `pipelines/`: Chained workflow execution and catalog.
  - `sentinel/`: Certificate, keystore, and Firebase expiration monitors.
  - `server_manager/`: Daemon lifecycle, systemd user services, and desktop launchers.
  - `qr/`: GF(256) Reed-Solomon pure Python QR code generator.
  - `config_modules/`: Workspace layout, Melos monorepo, and Dart pub workspaces.
- **Backward Compatibility**: If any file is relocated, leave a backward-compatibility module shim (`sys.modules[__name__] = _impl`) so no tests or scripts break.

### 2. Frontend (Vanilla JS + Design System)
- **Single Responsibility**: Never combine multiple feature domains into a single script.
- **Structured Sub-Folders**:
  - `features/deployment/frontend/modules/dashboard/`: Runtime feature controllers for the main deployment view (`app_workspace.js`, `app_sentinel.js`, `app_doctor.js`, `app_apk_qr.js`, `app_adb.js`, `app_profiler.js`, `app_cache_warmer.js`, `app_build_size.js`, `app_docs.js`, `app_server.js`, `app_demo.js`).
  - `features/deployment/frontend/modules/setup/`: Configure dialog tab controllers (`setup_scanner.js`, `setup_webhooks.js`, `setup_pipelines.js`, `setup_credentials.js`, `setup_github.js`).
- **No Build Step**: Plain vanilla JavaScript ES-friendly scripts loaded cleanly via `<script src="...">`.

### 3. Living Documentation
- Whenever code is added, updated, or reorganized, immediately update:
  - `README.md`
  - `ARCHITECTURE.md`
  - `FAQ.md` (living questions and new sections)
  - `docs/API.md`
  - In-app docs generator in `features/deployment/backend/docs_provider.py`
- All tests must remain 100% green (`python3 -m unittest discover tests`).
