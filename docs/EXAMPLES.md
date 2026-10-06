# End-to-End Workflow Examples & Architecture Flows 🚀

This guide provides practical, step-by-step walkthroughs of common mobile deployment scenarios, illustrating the complete data flow from the UI, through the Python REST API, to execution and distribution.

---

## 📑 Workflow Index
1. [Flow 1: First-Time Project Import & Auto-Scan](#flow-1-first-time-project-import--auto-scan)
2. [Flow 2: Multi-Environment Build (Dev / QA / Prod)](#flow-2-multi-environment-build-dev--qa--prod)
3. [Flow 3: Wireless Testing (Camera QR & Multi-Device ADB Push)](#flow-3-wireless-testing-camera-qr--multi-device-adb-push)
4. [Flow 4: Chained Release Pipeline (Doctor → Build → Inspect → Fastlane → Webhook)](#flow-4-chained-release-pipeline)
5. [Flow 5: Inbound CI/CD & Two-Way ChatOps (Slack / GitHub)](#flow-5-inbound-cicd--two-way-chatops)
6. [Flow 6: Pre-Release Sentinel & Build Size Diffing](#flow-6-pre-release-sentinel--build-size-diffing)

---

## Flow 1: First-Time Project Import & Auto-Scan

### Scenario
A developer opens the console and connects an existing multi-flavor Flutter monorepo with Android and iOS applications.

### Visual Flow
```
[User] ──> Enters folder path ──> [Inspect Path API] ──> Auto-detects layout & stacks
  │                                                           │
  ▼                                                           ▼
Click "Auto-Scan Project" ──> [Scan Config API] ──> Extracts flavors, IDs & keys
  │                                                           │
  ▼                                                           ▼
Click "Save Config" ──> [Generate Commands API] ──> Dynamic Dev/QA/Prod tiles ready
```

### Steps & API Sequence
1. **Directory Inspection**:
   ```bash
   curl -s -H "X-API-Token: $TOKEN" \
     "http://localhost:18112/api/deployment/inspect-path?path=/path/to/project"
   ```
   *Returns framework type (`flutter`), package manager (`melos` / `pub`), and detected app candidates.*

2. **Register Workspace**:
   ```bash
   curl -s -X POST -H "X-API-Token: $TOKEN" \
     -d '{"path": "/path/to/project"}' \
     "http://localhost:18112/api/deployment/workspace/allow"
   ```

3. **1-Click Auto-Scan**:
   ```bash
   curl -s -X POST -H "X-API-Token: $TOKEN" \
     -d '{"force": true}' \
     "http://localhost:18112/api/deployment/scan-all"
   ```
   *Automatically parses `build.gradle`, `.xcconfig`, Google Services JSONs, and `.p8` keys.*

---

## Flow 2: Multi-Environment Build (Dev / QA / Prod)

### Scenario
Compiling a development debug APK, a QA staging build, and a production release App Bundle.

### Steps & API Sequence
1. **Fetch Configured Commands for App**:
   ```bash
   curl -s -H "X-API-Token: $TOKEN" \
     "http://localhost:18112/api/deployment/commands?app=customer_app"
   ```

2. **Trigger Build Execution**:
   ```bash
   curl -s -X POST -H "X-API-Token: $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"app": "customer_app", "templateId": "build_apk", "flavor": "dev", "confirmed": true}' \
     "http://localhost:18112/api/deployment/execute"
   ```
   *Returns job descriptor with `jobId` and process group PID.*

3. **Stream Logs & Poll State**:
   ```bash
   curl -s -H "X-API-Token: $TOKEN" \
     "http://localhost:18112/api/deployment/job?id=<job_id>"
   ```

---

## Flow 3: Wireless Testing (Camera QR & Multi-Device ADB Push)

### Scenario
Immediately after compiling an Android APK or iOS IPA, installing it wirelessly on physical test devices without USB cables.

### Camera QR Scan
1. **Fetch Download Link & QR**:
   ```bash
   curl -s -H "X-API-Token: $TOKEN" \
     "http://localhost:18112/api/deployment/qr?text=http://192.168.1.10:18112/api/deployment/download/customer_app"
   ```
   *Generates pure Python SVG QR code. QA testers point their phone camera to download and install instantly.*

### Multi-Device Wireless ADB Push
1. **Discover Connected Wi-Fi Devices**:
   ```bash
   curl -s -H "X-API-Token: $TOKEN" \
     "http://localhost:18112/api/deployment/adb/devices"
   ```

2. **Parallel APK Push**:
   ```bash
   curl -s -X POST -H "X-API-Token: $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"app": "customer_app", "deviceIds": ["192.168.1.50:5555", "192.168.1.51:5555"]}' \
     "http://localhost:18112/api/deployment/adb/push"
   ```

---

## Flow 4: Chained Release Pipeline

### Scenario
An automated full release flow: Pre-flight checks → Build → Archive size verification → Store upload → Outgoing team notification.

### Visual Pipeline
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  App Doctor  │ ──> │  Build AAB   │ ──> │  Size Diff   │ ──> │ Upload Store │ ──> Slack / Teams
│ Pre-flight ✓ │     │ Compilation  │     │ Delta Check  │     │   Fastlane   │     Notification
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

1. **Trigger Saved Pipeline**:
   ```bash
   curl -s -X POST -H "X-API-Token: $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"app": "customer_app", "pipelineId": "full_prod_release", "flavor": "prod", "confirmed": true}' \
     "http://localhost:18112/api/deployment/pipelines/run"
   ```

2. **Fail-Fast Safety**:
   If any step fails (e.g. keystore expired or uncompressed asset detected), execution halts immediately before uploading corrupted binaries.

---

## Flow 5: Inbound CI/CD & Two-Way ChatOps

### Scenario
Triggering builds remotely from GitHub webhooks or Slack slash commands without opening the browser.

1. **Slack Slash Command**:
   ```
   /deploy customer_app prod build_aab
   ```

2. **GitHub Tag Push Webhook**:
   - Webhook URL: `http://server:18112/api/deployment/webhook/incoming/github`
   - Secret verification: Verified using HMAC SHA-256 (`X-Hub-Signature-256`).

---

## Flow 6: Pre-Release Sentinel & Build Size Diffing

### Scenario
Preventing release build failures caused by expired certificates or unexpected size regressions.

1. **Sentinel Certificate Audit**:
   ```bash
   curl -s -H "X-API-Token: $TOKEN" \
     "http://localhost:18112/api/deployment/sentinel?app=customer_app&flavor=prod"
   ```
   *Flags Apple distribution certs or Android upload keys expiring in ≤30 days.*

2. **In-Memory Central Directory Size Inspection**:
   ```bash
   curl -s -H "X-API-Token: $TOKEN" \
     "http://localhost:18112/api/deployment/build-size?app=customer_app&flavor=prod"
   ```
   *Diffs archive size against previous build and flags uncompressed raw assets (`ZIP_STORED` ≥ 500 KB).*
