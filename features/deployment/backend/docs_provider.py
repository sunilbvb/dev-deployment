"""
Documentation and server status provider for Dev Deployment Console.

Provides endpoints to serve markdown documentation files (README, ARCHITECTURE,
FAQ, API, proposals, etc.) and server diagnostic information directly to the
frontend documentation hub and offline welcome console.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Optional

from config import get_workspace_root

_START_TIME = time.time()

# Standard repository docs registry
DOC_REGISTRY: dict[str, dict[str, Any]] = {
    "overview": {
        "id": "overview",
        "title": "Console Overview & Quickstart",
        "description": "Comprehensive guide to all features, startup steps, and architecture.",
        "category": "Getting Started",
        "file": None,  # Dynamically generated
    },
    "readme": {
        "id": "readme",
        "title": "README — Dev Deployment",
        "description": "Main project guide, architecture overview, and setup instructions.",
        "category": "Repository Docs",
        "file": "README.md",
    },
    "architecture": {
        "id": "architecture",
        "title": "ARCHITECTURE & Design Decisions",
        "description": "System architecture, monorepo handling, and ADR decisions.",
        "category": "Repository Docs",
        "file": "ARCHITECTURE.md",
    },
    "faq": {
        "id": "faq",
        "title": "FAQ & Troubleshooting",
        "description": "Frequently asked questions, common errors, and best practices.",
        "category": "Repository Docs",
        "file": "FAQ.md",
    },
    "api": {
        "id": "api",
        "title": "REST API Documentation",
        "description": "Complete specification of all backend REST endpoints and schemas.",
        "category": "API & Technical",
        "file": "docs/API.md",
    },
    "pipelines": {
        "id": "pipelines",
        "title": "Pipelines Proposal (ADR 0001)",
        "description": "Saved pipelines architecture, step execution engine, and JSON schema.",
        "category": "Proposals & ADRs",
        "file": "docs/proposals/0001-pipelines.md",
    },
    "changelog": {
        "id": "changelog",
        "title": "CHANGELOG & Release Notes",
        "description": "Detailed log of features, fixes, and version releases.",
        "category": "Repository Docs",
        "file": "CHANGELOG.md",
    },
    "contributing": {
        "id": "contributing",
        "title": "CONTRIBUTING Guide",
        "description": "Contribution guidelines, coding standards, and testing procedures.",
        "category": "Guidelines",
        "file": "CONTRIBUTING.md",
    },
    "security": {
        "id": "security",
        "title": "SECURITY Policy",
        "description": "Security considerations, authentication tokens, and vulnerability reporting.",
        "category": "Guidelines",
        "file": "SECURITY.md",
    },
}


def _get_repo_root() -> Path:
    """Resolve the root of the dev-deployment git repository."""
    # features/deployment/backend/docs_provider.py -> 3 levels up
    cand = Path(__file__).resolve().parents[3]
    if (cand / "README.md").is_file() or (cand / "start.sh").is_file():
        return cand
    return get_workspace_root()


def list_available_docs() -> list[dict[str, Any]]:
    """Return all available documentation topics for the UI sidebar."""
    repo_root = _get_repo_root()
    results = []
    for doc_id, meta in DOC_REGISTRY.items():
        exists = True
        if meta["file"]:
            fpath = repo_root / meta["file"]
            exists = fpath.is_file()
        results.append({
            "id": doc_id,
            "title": meta["title"],
            "description": meta["description"],
            "category": meta["category"],
            "file": meta["file"],
            "available": exists,
        })
    return results


def _generate_overview_markdown(repo_root: Path) -> str:
    """Generate dynamic platform overview markdown."""
    return f"""# 🚀 Dev Deployment Console — Overview & Guide

Welcome to the **Dev Deployment Console** — a lightweight, zero-dependency developer dashboard and automation tool for Flutter and mobile application deployments across multiple environments (Dev, QA, Production).

---

## ⚡ Core Capabilities & Features

1. **Multi-App Flutter Deployments & Flavor Support**
   - Automatically detects single apps, Melos monorepos, and multi-app workspaces.
   - Generates and executes parameterized Fastlane & Flutter deployment commands.
   - Clean separation of Dev, QA, and Production environments with production deploy confirmation guards.

2. **Zero-Terminal Startup (1-Click Launchers)**
   - Create desktop application shortcuts (`.desktop`) with 1-click in the Server Console modal.
   - Install auto-start systemd user service to launch seamlessly on system login.

3. **Interactive Demo Mode & Offline Console**
   - Explore and test-drive simulated builds, pre-flight diagnostics, and size diffs even when the backend is offline.

4. **Visual Pipeline Builder & Saved Pipelines (Chained Workflows)**
   - Create and save multi-step deployment sequences with an interactive categorized step picker (Diagnostics, Builds, Uploads, Quality/Test, Custom Shell Commands).
   - Support for custom shell execution steps, drag/interactive step reordering, continue-on-failure safety, and live step-by-step progress tracking.

5. **Pre-flight "App Doctor" (1-Click Diagnostics)**
   - 1-click comprehensive system and project health evaluation before running long builds.
   - Inspects Flutter SDK, Android SDK, CocoaPods, keystores, `.p8` Apple keys, provisioning profiles, Git clean status, and Firebase configurations.

6. **Local APK Hosting & QR Code Scan-to-Install**
   - Instantly hosts completed Android `.apk` builds over local HTTP (`/api/deployment/download/<job_id>`).
   - Generates a terminal & UI QR code for instant phone camera scan-and-install over Wi-Fi without cables or Firebase App Distribution setup.

7. **Universal Webhooks & CI/CD Ingestion**
   - Automated deployment notifications to Slack, Discord, Microsoft Teams, Google Chat, and WhatsApp (Meta Cloud API + Twilio REST API).
   - Dynamic custom payload templating with variable interpolation (`{{app}}`, `{{status}}`, `{{flavor}}`, `{{version}}`, `{{commit}}`, `{{author}}`, etc.) and user-defined HTTP headers.
   - Universal incoming CI/CD ingestion gateway (`/api/deployment/webhook/incoming`) supporting GitHub Actions, GitLab CI/CD, Slack slash commands, and generic cURL triggers with HMAC SHA-256 and token authentication.

8. **Certificate & Keystore Expiry Sentinel**
   - Proactive warnings on dashboard:
     - Apple `.p8` API keys and distribution certificates expiring within 30 days.
     - Android upload keys nearing validity limits.
     - Cross-platform Firebase project ID mismatches (e.g. dev config in a production build).

9. **Build Size Inspector & Diff**
   - Fast archive size comparison against previous successful runs (`AAB: 24.2 MB (+3.8 MB, +18%) ⚠️`).
   - Deep zip central directory inspection without extracting files to disk.
   - Alerts developers if huge uncompressed raw assets (`ZIP_STORED` ≥ 500 KB) are accidentally packaged into production bundles.

---

## 🏁 Starting the Deployment Server

To connect this web console to your real local projects, start the backend server from your terminal or 1-click launcher:

```bash
# 1. From repository root:
./start.sh

# Or directly with Python:
python3 features/deployment/backend/server.py --port 18112
```

- **Default Port:** `http://localhost:18112`
- **Security:** Protected by local bearer auth token (`~/.config/dev-deployment/auth_token.txt`).
- **Zero Third-Party Dependencies:** Written in 100% Python standard library.

---

## 📚 Repository Documentation Index

| Document | Description |
| :--- | :--- |
| [`README.md`](file://{repo_root / 'README.md'}) | Project overview, directory layout, and quickstart guide. |
| [`ARCHITECTURE.md`](file://{repo_root / 'ARCHITECTURE.md'}) | Architecture principles, state management, and ADRs. |
| [`FAQ.md`](file://{repo_root / 'FAQ.md'}) | Troubleshooting, environment setup, and common solutions. |
| [`docs/API.md`](file://{repo_root / 'docs/API.md'}) | Backend REST API endpoints, parameters, and JSON responses. |
| [`CHANGELOG.md`](file://{repo_root / 'CHANGELOG.md'}) | Detailed version history and feature changelog. |
| [`CONTRIBUTING.md`](file://{repo_root / 'CONTRIBUTING.md'}) | Guidelines for testing, code style, and submitting pull requests. |
| [`SECURITY.md`](file://{repo_root / 'SECURITY.md'}) | Localhost token protection, CSRF headers, and security rules. |

---

*Tip: You can read any of these markdown documents using the sidebar on the left!*
"""


def get_doc_content(doc_id: str, ws_root: Optional[Path] = None) -> dict[str, Any]:
    """Retrieve markdown content for a requested document."""
    repo_root = ws_root or _get_repo_root()
    doc_meta = DOC_REGISTRY.get(doc_id.lower().strip())

    if not doc_meta:
        return {
            "success": False,
            "error": f"Unknown document '{doc_id}'. Available docs: {', '.join(DOC_REGISTRY.keys())}",
            "availableDocs": list_available_docs(),
        }

    if doc_id.lower() == "overview" or not doc_meta.get("file"):
        content = _generate_overview_markdown(repo_root)
        return {
            "success": True,
            "doc": doc_id,
            "title": doc_meta["title"],
            "category": doc_meta["category"],
            "filename": "Overview",
            "content": content,
            "availableDocs": list_available_docs(),
        }

    file_rel = doc_meta["file"]
    target_path = (repo_root / file_rel).resolve()

    # Security: Ensure target file is within repo_root or workspace_root and has .md suffix
    allowed_roots = [repo_root.resolve()]
    try:
        allowed_roots.append(get_workspace_root().resolve())
    except Exception:
        pass

    is_safe = False
    for root in allowed_roots:
        try:
            target_path.relative_to(root)
            is_safe = True
            break
        except ValueError:
            pass

    if not is_safe or target_path.suffix.lower() != ".md":
        return {
            "success": False,
            "error": "Access to requested file path is restricted.",
            "availableDocs": list_available_docs(),
        }

    if not target_path.is_file():
        return {
            "success": False,
            "error": f"Documentation file '{file_rel}' does not exist on disk.",
            "doc": doc_id,
            "title": doc_meta["title"],
            "availableDocs": list_available_docs(),
        }

    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
        return {
            "success": True,
            "doc": doc_id,
            "title": doc_meta["title"],
            "category": doc_meta["category"],
            "filename": target_path.name,
            "filePath": str(target_path),
            "content": content,
            "availableDocs": list_available_docs(),
        }
    except Exception as exc:
        logging.exception("Failed to read doc file %s", target_path)
        return {
            "success": False,
            "error": f"Failed to read file: {exc}",
            "availableDocs": list_available_docs(),
        }


def get_server_status_info(port: int = 18112, ws_root: Optional[Path] = None) -> dict[str, Any]:
    """Diagnostic info about currently running deployment backend server."""
    ws = ws_root or get_workspace_root()
    repo_root = _get_repo_root()
    uptime_sec = int(time.time() - _START_TIME)

    return {
        "success": True,
        "status": "online",
        "port": port,
        "pid": os.getpid(),
        "uptimeSeconds": uptime_sec,
        "pythonVersion": sys.version.split()[0],
        "workspaceRoot": str(ws),
        "repoRoot": str(repo_root),
        "commandToStart": "./start.sh",
        "directPythonCommand": f"python3 features/deployment/backend/server.py --port {port}",
    }
