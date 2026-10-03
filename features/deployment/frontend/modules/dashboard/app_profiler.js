/**
 * app_profiler.js — Build Time Profiler & Compilation Bottleneck Heatmap Module
 * Handles:
 * 1. Inspecting build output logs and categorizing into 6 phases
 * 2. Visual progress bar segmented heatmap
 * 3. Flagging compilation bottlenecks (>=30%) with optimization tips
 */

let currentProfileInfo = null;

async function checkAndDisplayBuildProfile(jobId) {
    try {
        const res = await fetch(api(`/api/deployment/build-profile?id=${encodeURIComponent(jobId || '')}`));
        const data = await res.json();
        if (data.success && data.phases) {
            currentProfileInfo = data;
            if (els.buildProfilerBanner) {
                if (els.buildProfilerSummaryText) {
                    els.buildProfilerSummaryText.textContent = `Build Profile: ${data.summary}`;
                }
                if (els.buildProfilerSubtext) {
                    els.buildProfilerSubtext.textContent = `Total Time: ${data.totalDurationSeconds}s · ${data.phases.length} phases profiled`;
                }
                els.buildProfilerBanner.classList.remove('hidden');
                els.buildProfilerBanner.style.display = 'block';
                if (typeof refreshIcons === 'function') refreshIcons();
            }
        }
    } catch (err) {
        console.warn('Could not inspect build profile:', err);
    }
}

function openBuildProfilerModal(profileData = currentProfileInfo) {
    if (!profileData) return;
    if (els.bpTotalDurationText) {
        els.bpTotalDurationText.textContent = `${profileData.totalDurationSeconds}s Total`;
    }
    if (els.bpSummaryText) {
        els.bpSummaryText.textContent = profileData.summary || 'Build timings';
    }
    if (els.bpFooterJobInfo) {
        els.bpFooterJobInfo.textContent = `Job: ${profileData.jobId || 'latest'} · ${profileData.app || ''} (${profileData.flavor || ''})`;
    }

    // Render horizontal progress bar segments
    if (els.bpProgressBar && profileData.phases) {
        els.bpProgressBar.innerHTML = profileData.phases.map(p => {
            if (p.percentage <= 0) return '';
            return `<div style="width:${p.percentage}%; background:${p.color}; height:100%; transition:width 0.3s;" title="${escapeHtml(p.name)}: ${p.durationSeconds}s (${p.percentage}%)"></div>`;
        }).join('');
    }

    // Render bottleneck cards
    if (els.bpBottlenecksContainer) {
        if (profileData.bottlenecks && profileData.bottlenecks.length > 0) {
            els.bpBottlenecksContainer.innerHTML = profileData.bottlenecks.map(b => `
                <div style="background:rgba(245, 158, 11, 0.1); border:1px solid #f59e0b; border-radius:6px; padding:10px 14px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-weight:700; font-size:0.85rem; color:#f59e0b;">⚠️ Bottleneck: ${escapeHtml(b.phaseName)} (${b.percentage}%)</span>
                        <span class="ui-badge" data-variant="warning">${b.severity.toUpperCase()}</span>
                    </div>
                    <div style="font-size:0.78rem; color:var(--ui-text-muted); line-height:1.4;">
                        💡 <strong>Optimization Tip:</strong> ${escapeHtml(b.tip)}
                    </div>
                </div>
            `).join('');
        } else {
            els.bpBottlenecksContainer.innerHTML = `
                <div style="background:rgba(16, 185, 129, 0.1); border:1px solid #10b981; border-radius:6px; padding:10px 14px; font-size:0.82rem; color:#10b981;">
                    ✓ No significant compile bottlenecks detected. Timing is balanced across build phases.
                </div>`;
        }
    }

    // Render phase table
    if (els.bpTableBody && profileData.phases) {
        els.bpTableBody.innerHTML = profileData.phases.map(p => `
            <tr style="border-top:1px solid var(--ui-border-color);">
                <td style="padding:10px 14px; font-weight:600; display:flex; align-items:center; gap:8px;">
                    <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${p.color};"></span>
                    <span>${escapeHtml(p.name)}</span>
                </td>
                <td style="padding:10px 14px; font-family:monospace;">${p.durationSeconds}s</td>
                <td style="padding:10px 14px; font-weight:700;">${p.percentage}%</td>
                <td style="padding:10px 14px; color:var(--ui-text-muted); font-size:0.78rem;">${escapeHtml(p.tip || '-')}</td>
            </tr>
        `).join('');
    }

    if (els.buildProfilerModalOverlay) {
        els.buildProfilerModalOverlay.classList.add('ui-active');
    }
    if (typeof refreshIcons === 'function') refreshIcons();
}

function closeBuildProfilerModal() {
    if (els.buildProfilerModalOverlay) {
        els.buildProfilerModalOverlay.classList.remove('ui-active');
    }
}

// ═════════════════════════════════════════════════════════════════════
// Wire Events
// ═════════════════════════════════════════════════════════════════════
if (els.buildProfilerBanner) els.buildProfilerBanner.addEventListener('click', () => openBuildProfilerModal());
if (els.closeBuildProfilerModalBtn) els.closeBuildProfilerModalBtn.addEventListener('click', closeBuildProfilerModal);
if (els.closeBuildProfilerBtn) els.closeBuildProfilerBtn.addEventListener('click', closeBuildProfilerModal);
if (els.buildProfilerModalOverlay) {
    els.buildProfilerModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.buildProfilerModalOverlay) closeBuildProfilerModal();
    });
}

// Global exports
window.currentProfileInfo = currentProfileInfo;
window.checkAndDisplayBuildProfile = checkAndDisplayBuildProfile;
window.openBuildProfilerModal = openBuildProfilerModal;
window.closeBuildProfilerModal = closeBuildProfilerModal;
