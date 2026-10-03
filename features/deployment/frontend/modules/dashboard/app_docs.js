/**
 * app_docs.js — Documentation & Knowledge Hub Module
 * Renders embedded and server-fetched markdown documentation with code syntax,
 * handles docs modal lifecycle, navigation, and sidebar doc selection.
 */

const DEFAULT_EMBEDDED_DOCS = {
    overview: {
        title: "Console Overview & Quickstart",
        category: "Getting Started",
        filename: "Overview",
        content: `# 🚀 Dev Deployment Console — Overview & Guide

Welcome to the **Dev Deployment Console** — a lightweight, zero-dependency developer dashboard and automation tool for Flutter and mobile application deployments across multiple environments (Dev, QA, Production).

---

## ⚡ Core Capabilities & Features

1. **Multi-App Flutter Deployments & Flavor Support**
   - Automatically detects single apps, Melos monorepos, and multi-app workspaces.
   - Generates and executes parameterized Fastlane & Flutter deployment commands.
   - Clean separation of Dev, QA, and Production environments with production deploy confirmation guards.

2. **Saved Pipelines (Chained Workflows)**
   - Create and save multi-step deployment sequences (e.g. \`Pre-flight Diagnostics\` → \`Build AAB\` → \`Upload to Play Store\`).
   - Stop-on-failure safety and live step-by-step progress tracking.

3. **Pre-flight "App Doctor" (1-Click Diagnostics)**
   - 1-click comprehensive system and project health evaluation before running long builds.
   - Inspects Flutter SDK, Android SDK, CocoaPods, keystores, \`.p8\` Apple keys, provisioning profiles, Git clean status, and Firebase configurations.

4. **Local APK Hosting & QR Code Scan-to-Install**
   - Instantly hosts completed Android \`.apk\` builds over local HTTP (\`/api/deployment/download/<job_id>\`).
   - Generates a terminal & UI QR code for instant phone camera scan-and-install over Wi-Fi without cables or Firebase App Distribution setup.

5. **Outgoing Webhooks (Slack / Discord / Microsoft Teams)**
   - Automated deployment notifications to team channels on build completion or failure.
   - Rich card layouts with status badges, elapsed duration, commit logs, and direct APK download links.

6. **Certificate & Keystore Expiry Sentinel**
   - Proactive warnings on dashboard:
     - Apple \`.p8\` API keys and distribution certificates expiring within 30 days.
     - Android upload keys nearing validity limits.
     - Cross-platform Firebase project ID mismatches (e.g. dev config in a production build).

7. **Build Size Inspector & Diff**
   - Fast archive size comparison against previous successful runs (\`AAB: 24.2 MB (+3.8 MB, +18%) ⚠️\`).
   - Deep zip central directory inspection without extracting files to disk.
   - Alerts developers if huge uncompressed raw assets (\`ZIP_STORED\` ≥ 500 KB) are accidentally packaged into production bundles.

---

## 🏁 Starting the Deployment Server

To connect this web console to your real local projects, start the backend server from your terminal:

\`\`\`bash
# 1. From repository root:
./start.sh

# Or directly with Python:
python3 features/deployment/backend/server.py --port 18112
\`\`\`

- **Default Port:** \`http://localhost:18112\`
- **Security:** Protected by local bearer auth token (\`~/.config/dev-deployment/auth_token.txt\`).
- **Zero Third-Party Dependencies:** Written in 100% Python standard library.
`
    },
    readme: {
        title: "README — Dev Deployment",
        category: "Repository Docs",
        filename: "README.md",
        content: `# Dev Deployment Console

A zero-dependency, local-first developer dashboard for automating Flutter & mobile builds, Fastlane scripts, diagnostics, and team delivery.

## Key Highlights
- **Zero Third-Party Python Dependencies**: Runs purely on Python standard library (\`http.server\`, \`zipfile\`, \`json\`, \`subprocess\`).
- **Monorepo & Single-App Support**: Auto-detects Flutter apps with or without Melos.
- **Local APK Server & QR Code**: Scan phone camera to download test builds over local Wi-Fi.
- **Pre-flight App Doctor**: Prevents failed 20-minute CI builds by diagnosing environment issues upfront.
- **Build Size Inspector**: Compares APK/AAB size deltas and detects uncompressed assets.
`
    },
    architecture: {
        title: "ARCHITECTURE & Design Decisions",
        category: "Repository Docs",
        filename: "ARCHITECTURE.md",
        content: `# System Architecture & Principles

## 1. Zero External Dependencies (ADR 0001)
No \`pip install\`, no Node.js runtime for backend. Anyone with Python 3.10+ can clone and run immediately via \`./start.sh\`.

## 2. Local-First Execution
All commands are generated as transparent shell / Fastlane commands executed locally under user privileges.

## 3. Tab-Isolated Workspaces (C9)
Every browser tab carries an \`X-Workspace\` header so multiple monorepos can be monitored independently without race conditions.

## 4. Security Guards
- Localhost only (DNS rebinding rejected).
- CSRF Origin check on all mutating endpoints.
- Path traversal sanitization on all artifact and credential downloads.
`
    },
    faq: {
        title: "FAQ & Troubleshooting",
        category: "Repository Docs",
        filename: "FAQ.md",
        content: `# Frequently Asked Questions

### Q: Why do I see "Server Offline" when opening index.html?
A: Web browsers run \`file://\` in a strict sandbox. To communicate with local Flutter projects, start the Python server using \`./start.sh\`.

### Q: How do I scan the QR code from my phone?
A: Make sure your phone is connected to the same Wi-Fi network as your development computer. The console automatically detects your LAN IP (e.g. \`http://192.168.1.50:18112\`).

### Q: How do I configure Slack or Discord webhooks?
A: Open the **Configure** dialog (top right), navigate to the **Notifications** tab, and enter your webhook URL.
`
    },
    api: {
        title: "REST API Documentation",
        category: "API & Technical",
        filename: "docs/API.md",
        content: `# REST API Specification

### GET /api/deployment/server-status
Returns heartbeat, port, process PID, and uptime. Public health ping.

### GET /api/deployment/workspaces
Returns all configured and discovered workspace paths.

### GET /api/deployment/apps
Returns detected Flutter apps in active workspace.

### GET /api/deployment/doctor?app=<app>&flavor=<flavor>
Runs comprehensive 6-category pre-flight diagnostics.

### GET /api/deployment/build-size?app=<app>&flavor=<flavor>
Returns build artifact size delta and uncompressed assets diff.

### GET /api/deployment/docs?doc=<id>
Returns rendered markdown content for repository documentation.
`
    },
    pipelines: {
        title: "Pipelines Proposal (ADR 0001)",
        category: "Proposals & ADRs",
        filename: "0001-pipelines.md",
        content: `# 🔀 Saved Pipelines Architecture (ADR 0001)

Saved Pipelines chain multi-step build, verification, and release steps into a single 1-click execution flow.

---

## ⚡ Core Concepts
- **Sequential Execution**: Steps execute one after another in order.
- **Fail-Fast Safety**: If a step fails, the pipeline aborts immediately to prevent uploading corrupted builds.
- **Step Templates**: Mix pre-configured templates (\`flutter build appbundle\`, \`fastlane android upload_aab\`) with custom shell commands.
- **Visual Progress**: Each step card updates with spinning, pass, or fail states in real time.
`
    },
    changelog: {
        title: "CHANGELOG & Release Notes",
        category: "Repository Docs",
        filename: "CHANGELOG.md",
        content: `# 📋 CHANGELOG & Feature Highlights

## Recent Milestones:
- **Documentation & Knowledge Hub**: Built-in markdown documentation viewer and offline quickstart guide.
- **Local APK Hosting & QR Code**: Serve debug/QA builds over local HTTP with instant phone camera install.
- **Outgoing Webhooks**: Automated notifications for Slack, Discord, and Microsoft Teams.
- **Certificate & Keystore Sentinel**: Proactive expiry warnings for Apple .p8 keys and Android upload keystores.
- **Build Size Inspector & Diff**: Instant APK/AAB size regression alerts and uncompressed assets detector.
`
    },
    security: {
        title: "SECURITY Policy & Architecture",
        category: "Guidelines",
        filename: "SECURITY.md",
        content: `# 🔒 SECURITY Policy & Architectural Controls

## Security Model:
- **Zero External Dependencies**: Pure Python standard library backend (\`http.server\`, \`hmac\`, \`secrets\`).
- **Bearer Token Auth**: All mutating API endpoints require valid \`X-API-Token\` generated on startup.
- **Host & Rebinding Protection**: Validates \`Host\` and \`Origin\` headers to reject DNS rebinding attacks.
- **Path Traversal Guards**: Strictly enforces resolved canonical paths within allowed workspace boundaries.
`
    }
};

function renderSimpleMarkdown(md) {
    if (!md) return '';
    let html = escapeHtml(md);

    // Fenced code blocks ```lang ... ```
    html = html.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (_, lang, code) => {
        const langLabel = lang ? `<span style="font-size:0.7rem; text-transform:uppercase; opacity:0.6; margin-bottom:4px; display:block;">${lang}</span>` : '';
        return `<div class="code-block-container" style="background:#0f172a; padding:12px 14px; border-radius:8px; margin:12px 0; border:1px solid rgba(255,255,255,0.08); font-family:monospace; font-size:0.82rem; overflow-x:auto;">${langLabel}<pre style="margin:0; color:#e2e8f0; white-space:pre-wrap;">${code}</pre></div>`;
    });

    // Inline code `...`
    html = html.replace(/`([^`\n]+)`/g, '<code style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-family:monospace; font-size:0.85em; color:var(--ui-primary, #6366f1);">$1</code>');

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h4 style="font-size:1.05rem; font-weight:700; margin:16px 0 6px; color:var(--ui-text-primary);">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="font-size:1.25rem; font-weight:700; margin:22px 0 10px; border-bottom:1px solid var(--ui-border-color); padding-bottom:6px; color:var(--ui-text-primary);">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 style="font-size:1.5rem; font-weight:800; margin:0 0 14px; color:var(--ui-text-primary);">$1</h2>');

    // Horizontal Rules
    html = html.replace(/^---$/gim, '<hr style="border:0; border-top:1px solid var(--ui-border-color); margin:18px 0;">');

    // Bold & Italics
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Links [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--ui-primary, #6366f1); text-decoration:underline;">$1</a>');

    // Unordered lists
    html = html.replace(/^\s*-\s+(.*$)/gim, '<li style="margin:4px 0;">$1</li>');
    html = html.replace(/(<li style="margin:4px 0;">.*<\/li>\s*)+/g, '<ul style="padding-left:20px; margin:8px 0 12px;">$&</ul>');

    // Blockquotes
    html = html.replace(/^>\s+(.*$)/gim, '<blockquote style="border-left:4px solid var(--ui-primary, #6366f1); padding:8px 14px; margin:12px 0; background:rgba(99,102,241,0.06); border-radius:0 6px 6px 0; font-size:0.85rem;">$1</blockquote>');

    // Paragraphs (lines separated by double breaks)
    return html.split(/\n\n+/).map(p => {
        p = p.trim();
        if (!p) return '';
        if (p.startsWith('<h') || p.startsWith('<div') || p.startsWith('<ul') || p.startsWith('<hr') || p.startsWith('<blockquote')) {
            return p;
        }
        return `<p style="margin:8px 0; line-height:1.6;">${p.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');
}

async function openDocsModal(docId = 'overview') {
    state.activeDocId = docId;
    if (els.docsModalOverlay) {
        els.docsModalOverlay.classList.add('ui-active');
    }
    await loadDoc(docId);
    refreshIcons();
}

function closeDocsModal() {
    if (els.docsModalOverlay) {
        els.docsModalOverlay.classList.remove('ui-active');
    }
}

async function loadDoc(docId) {
    state.activeDocId = docId;

    // Update active state in sidebar
    if (els.docsModalOverlay) {
        els.docsModalOverlay.querySelectorAll('.docs-nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-doc') === docId);
        });
    }

    if (els.docsContentArea) {
        els.docsContentArea.innerHTML = '<div style="padding:20px; color:var(--ui-muted); text-align:center;">Loading document...</div>';
    }

    let docData = state.cachedDocs[docId];

    if (!docData) {
        try {
            const res = await fetch(api(`/api/deployment/docs?doc=${encodeURIComponent(docId)}`));
            const data = await res.json();
            if (data.success && data.content) {
                docData = data;
                state.cachedDocs[docId] = data;
            }
        } catch (_) {
            // Server offline or fetch failed - fall back to embedded docs
        }
    }

    if (!docData) {
        docData = DEFAULT_EMBEDDED_DOCS[docId] || DEFAULT_EMBEDDED_DOCS['overview'];
    }

    if (els.docsCurrentTitle) els.docsCurrentTitle.textContent = docData.title || docId;
    if (els.docsCurrentCategory) els.docsCurrentCategory.textContent = docData.category || 'Documentation';
    if (els.docsCurrentFilename) els.docsCurrentFilename.textContent = docData.filename || `${docId}.md`;
    if (els.docsFooterPath) els.docsFooterPath.textContent = docData.filePath || `Doc: ${docData.filename || docId}`;

    if (els.docsContentArea) {
        els.docsContentArea.innerHTML = renderSimpleMarkdown(docData.content);
    }
}

// Wire Event Listeners
if (els.openDocsBtn) {
    els.openDocsBtn.addEventListener('click', () => openDocsModal('overview'));
}
if (els.bannerOpenDocsBtn) {
    els.bannerOpenDocsBtn.addEventListener('click', () => openDocsModal('overview'));
}
if (els.closeDocsModalBtn) {
    els.closeDocsModalBtn.addEventListener('click', closeDocsModal);
}
if (els.closeDocsBtn) {
    els.closeDocsBtn.addEventListener('click', closeDocsModal);
}
if (els.docsModalOverlay) {
    els.docsModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.docsModalOverlay) closeDocsModal();
        const navBtn = e.target.closest('.docs-nav-item');
        if (navBtn) {
            loadDoc(navBtn.getAttribute('data-doc'));
        }
    });
}

// Window exports
window.DEFAULT_EMBEDDED_DOCS = DEFAULT_EMBEDDED_DOCS;
window.renderSimpleMarkdown = renderSimpleMarkdown;
window.openDocsModal = openDocsModal;
window.closeDocsModal = closeDocsModal;
window.loadDoc = loadDoc;
