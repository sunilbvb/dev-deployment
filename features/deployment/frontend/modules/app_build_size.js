/**
 * app_build_size.js — Build Size Inspector & Diff Module
 * Compares artifact sizes (AAB, APK, IPA) against previous runs,
 * inspects zip archives for uncompressed assets, and renders diff breakdown.
 */

let currentBuildSizeInfo = null;

async function checkAndDisplayBuildSize(jobId, app = '', flavor = '') {
    if (!els.buildSizeBanner) return;
    try {
        const res = await fetch(api(`/api/deployment/build-size?jobId=${encodeURIComponent(jobId || '')}&app=${encodeURIComponent(app || '')}&flavor=${encodeURIComponent(flavor || '')}`));
        const data = await res.json();
        if (data.success && data.buildSize) {
            currentBuildSizeInfo = data.buildSize;
            renderBuildSizeBanner(data.buildSize);
        } else {
            els.buildSizeBanner.style.display = 'none';
            els.buildSizeBanner.classList.add('hidden');
        }
    } catch (err) {
        console.warn('Could not inspect build size:', err);
    }
}

function renderBuildSizeBanner(bs) {
    if (!els.buildSizeBanner || !bs) return;
    const severity = bs.severity || 'ok';
    els.buildSizeBanner.dataset.status = severity === 'critical' ? 'error' : (severity === 'warning' ? 'warning' : 'ok');
    if (els.buildSizeSummaryText) {
        els.buildSizeSummaryText.textContent = `Build Size: ${bs.summary || (bs.artifactType + ': ' + bs.currentSizeFormatted)}`;
    }
    if (els.buildSizeSubtext) {
        const alertNote = (bs.warnings && bs.warnings.length > 0) ? bs.warnings[0] : (bs.hasBaseline ? `Compared to previous build (${bs.previousBuild?.sizeFormatted || ''})` : 'First recorded baseline for this app');
        els.buildSizeSubtext.textContent = alertNote;
    }
    if (els.buildSizeBadge) {
        els.buildSizeBadge.setAttribute('data-variant', bs.badgeVariant || 'secondary');
        els.buildSizeBadge.textContent = severity === 'critical' ? '🚨 Inspect Bloat' : (severity === 'warning' ? '⚠️ Inspect Diff' : 'Inspect Size & Diff →');
    }
    els.buildSizeBanner.style.display = 'block';
    els.buildSizeBanner.classList.remove('hidden');
}

function openBuildSizeModal(bs = null) {
    const info = bs || currentBuildSizeInfo;
    if (!info || !els.buildSizeModalOverlay) return;

    if (els.buildSizeModalBadge) {
        els.buildSizeModalBadge.setAttribute('data-variant', info.badgeVariant || 'secondary');
        els.buildSizeModalBadge.textContent = (info.severity || 'ok').toUpperCase();
    }
    if (els.buildSizeModalSubtitle) {
        els.buildSizeModalSubtitle.textContent = `${info.artifactType || 'Artifact'} · ${info.currentFilename || ''}`;
    }

    if (els.bsStatCurrentSize) els.bsStatCurrentSize.textContent = info.currentSizeFormatted || '-';
    if (els.bsStatCurrentType) els.bsStatCurrentType.textContent = info.artifactType || '-';
    if (els.bsStatPreviousSize) els.bsStatPreviousSize.textContent = info.previousBuild ? info.previousBuild.sizeFormatted : 'None';
    if (els.bsStatPreviousMeta) els.bsStatPreviousMeta.textContent = info.previousBuild ? (info.previousBuild.jobId ? `Job #${info.previousBuild.jobId}` : 'Previous run') : 'First baseline';
    if (els.bsStatDelta) els.bsStatDelta.textContent = info.hasBaseline ? info.deltaFormatted : '0 B';
    if (els.bsStatPercent) {
        els.bsStatPercent.textContent = info.hasBaseline ? info.deltaPercentFormatted : 'Baseline';
        if (info.deltaBytes > 0) {
            els.bsStatPercent.style.color = info.severity === 'critical' ? 'var(--ui-danger, #ef4444)' : (info.severity === 'warning' ? 'var(--ui-warning, #f59e0b)' : 'var(--ui-text-muted)');
        } else if (info.deltaBytes < 0) {
            els.bsStatPercent.style.color = 'var(--ui-success, #22c55e)';
        } else {
            els.bsStatPercent.style.color = 'var(--ui-text-muted)';
        }
    }
    if (els.bsStatCompression) {
        els.bsStatCompression.textContent = (info.inspection && info.inspection.compressionRatio != null) ? `${info.inspection.compressionRatio}%` : '—';
    }
    if (els.bsStatUncompressed) {
        els.bsStatUncompressed.textContent = (info.inspection && info.inspection.totalUncompressedFormatted) ? `${info.inspection.totalUncompressedFormatted} uncompressed` : '—';
    }

    // Warnings and Bloat alerts
    if (els.buildSizeWarningsContainer) {
        const warnings = info.warnings || [];
        const uncompressed = info.inspection?.uncompressedAssets || [];
        if (warnings.length === 0 && uncompressed.length === 0) {
            els.buildSizeWarningsContainer.innerHTML = `
                <div class="ui-card" style="padding:10px 14px; background: rgba(34, 197, 94, 0.08); border-left: 4px solid var(--ui-success, #22c55e); font-size:0.82rem; color:var(--ui-success, #22c55e); display:flex; align-items:center; gap:8px;">
                    <i data-lucide="check-circle" style="width:16px;height:16px;"></i>
                    <span>No size bloat or uncompressed asset warnings detected.</span>
                </div>
            `;
        } else {
            let warnHtml = '';
            warnings.forEach(w => {
                const isCrit = info.severity === 'critical';
                const borderCol = isCrit ? 'var(--ui-danger, #ef4444)' : 'var(--ui-warning, #f59e0b)';
                const bgCol = isCrit ? 'rgba(239, 68, 68, 0.08)' : 'rgba(245, 158, 11, 0.08)';
                warnHtml += `
                    <div class="ui-card" style="padding:10px 14px; background:${bgCol}; border-left: 4px solid ${borderCol}; font-size:0.82rem; display:flex; align-items:center; gap:8px;">
                        <span style="font-size:1.1rem; line-height:1;">${isCrit ? '🚨' : '⚠️'}</span>
                        <div><strong>${escapeHtml(w)}</strong></div>
                    </div>
                `;
            });
            if (uncompressed.length > 0) {
                const filesList = uncompressed.map(u => `<li><code>${escapeHtml(u.name)}</code> (${escapeHtml(u.sizeFormatted)}) - <em>uncompressed (STORED)</em></li>`).join('');
                warnHtml += `
                    <div class="ui-card" style="padding:10px 14px; background: rgba(245, 158, 11, 0.08); border-left: 4px solid var(--ui-warning, #f59e0b); font-size:0.82rem;">
                        <div style="font-weight:600; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                            <span>⚠️ Huge Uncompressed Asset Bloat Detected</span>
                        </div>
                        <div style="opacity:0.9; margin-bottom:6px;">These files were packaged with zero compression (stored raw) inside the archive:</div>
                        <ul style="margin:0; padding-left:18px;">${filesList}</ul>
                    </div>
                `;
            }
            els.buildSizeWarningsContainer.innerHTML = warnHtml;
        }
    }

    renderBuildSizeDiffTable(info.diff);
    renderBuildSizeLargestTable(info.inspection?.largestFiles || []);

    if (els.bsModalFooterPath) {
        els.bsModalFooterPath.textContent = info.currentArtifactPath || '-';
        els.bsModalFooterPath.title = info.currentArtifactPath || '';
    }

    switchBuildSizeTab('diff');
    els.buildSizeModalOverlay.classList.add('ui-active');
    refreshIcons();
}

function renderBuildSizeDiffTable(diff) {
    if (!els.bsDiffTableContainer) return;
    if (!diff || !diff.hasDiff || (!diff.addedAssets.length && !diff.removedAssets.length && !diff.grownAssets.length)) {
        els.bsDiffTableContainer.innerHTML = `
            <div style="padding: 24px; text-align: center; color: var(--ui-muted, #9aa6b8); font-size: 0.85rem;">
                No file-level archive diff available (either this is the first baseline build, or previous build artifact was removed from disk).
            </div>
        `;
        return;
    }

    let rowsHtml = '';

    (diff.grownAssets || []).forEach(item => {
        const isGrowth = item.deltaBytes > 0;
        const badgeVar = isGrowth ? 'warning' : 'success';
        const sign = isGrowth ? '+' : '';
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all;">${escapeHtml(item.name)}</td>
                <td style="padding: 8px 12px;"><span class="ui-badge" data-variant="${badgeVar}">${isGrowth ? 'MODIFIED (+)' : 'SHRUNK (-)'}</span></td>
                <td style="padding: 8px 12px; font-family: monospace;">${escapeHtml(item.currSizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">${escapeHtml(item.prevSizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600; color: ${isGrowth ? 'var(--ui-warning, #f59e0b)' : 'var(--ui-success, #22c55e)'};">${sign}${escapeHtml(item.deltaFormatted)}</td>
            </tr>
        `;
    });

    (diff.addedAssets || []).forEach(item => {
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all;">${escapeHtml(item.name)}</td>
                <td style="padding: 8px 12px;"><span class="ui-badge" data-variant="info">NEW ASSET</span></td>
                <td style="padding: 8px 12px; font-family: monospace;">${escapeHtml(item.sizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">—</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600; color: var(--ui-info, #0ea5e9);">+${escapeHtml(item.sizeFormatted)}</td>
            </tr>
        `;
    });

    (diff.removedAssets || []).forEach(item => {
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all; opacity: 0.7;">${escapeHtml(item.name)}</td>
                <td style="padding: 8px 12px;"><span class="ui-badge" data-variant="secondary">REMOVED</span></td>
                <td style="padding: 8px 12px; font-family: monospace; opacity: 0.7;">—</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">${escapeHtml(item.sizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600; color: var(--ui-success, #22c55e); italic;">-${escapeHtml(item.sizeFormatted)}</td>
            </tr>
        `;
    });

    els.bsDiffTableContainer.innerHTML = `
        <div style="max-height: 280px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.72rem; text-transform: uppercase; color: var(--ui-muted, #9aa6b8);">
                        <th style="padding: 8px 12px;">Asset / File Path</th>
                        <th style="padding: 8px 12px; width: 110px;">Status</th>
                        <th style="padding: 8px 12px; width: 90px;">Current</th>
                        <th style="padding: 8px 12px; width: 90px;">Previous</th>
                        <th style="padding: 8px 12px; width: 90px;">Delta</th>
                    </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>
    `;
}

function renderBuildSizeLargestTable(files) {
    if (!els.bsLargestTableContainer) return;
    if (!files || files.length === 0) {
        els.bsLargestTableContainer.innerHTML = `
            <div style="padding: 24px; text-align: center; color: var(--ui-muted, #9aa6b8); font-size: 0.85rem;">
                No archive asset details available.
            </div>
        `;
        return;
    }

    let rowsHtml = '';
    files.forEach((f, idx) => {
        const isStored = f.compressType === 'stored';
        const methodBadge = isStored ? '<span class="ui-badge" data-variant="warning">STORED (0%)</span>' : '<span class="ui-badge" data-variant="secondary">Deflated</span>';
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; color: var(--ui-muted, #9aa6b8); width: 30px;">#${idx + 1}</td>
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all;">${escapeHtml(f.name)}</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600;">${escapeHtml(f.compressedSizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">${escapeHtml(f.uncompressedSizeFormatted)}</td>
                <td style="padding: 8px 12px;">${methodBadge}</td>
            </tr>
        `;
    });

    els.bsLargestTableContainer.innerHTML = `
        <div style="max-height: 280px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.72rem; text-transform: uppercase; color: var(--ui-muted, #9aa6b8);">
                        <th style="padding: 8px 12px; width: 30px;">#</th>
                        <th style="padding: 8px 12px;">File Inside Archive</th>
                        <th style="padding: 8px 12px; width: 110px;">Compressed</th>
                        <th style="padding: 8px 12px; width: 110px;">Uncompressed</th>
                        <th style="padding: 8px 12px; width: 110px;">Storage</th>
                    </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>
    `;
}

function switchBuildSizeTab(tab) {
    if (tab === 'diff') {
        if (els.bsTabDiffBtn) els.bsTabDiffBtn.setAttribute('data-variant', 'primary');
        if (els.bsTabLargestBtn) els.bsTabLargestBtn.setAttribute('data-variant', 'secondary');
        if (els.bsDiffTableView) els.bsDiffTableView.style.display = 'block';
        if (els.bsLargestTableView) els.bsLargestTableView.style.display = 'none';
    } else {
        if (els.bsTabDiffBtn) els.bsTabDiffBtn.setAttribute('data-variant', 'secondary');
        if (els.bsTabLargestBtn) els.bsTabLargestBtn.setAttribute('data-variant', 'primary');
        if (els.bsDiffTableView) els.bsDiffTableView.style.display = 'none';
        if (els.bsLargestTableView) els.bsLargestTableView.style.display = 'block';
    }
}

function closeBuildSizeModal() {
    if (els.buildSizeModalOverlay) {
        els.buildSizeModalOverlay.classList.remove('ui-active');
    }
}

async function openBuildSizeModalForTarget(targetId, app = '', flavor = '') {
    try {
        const res = await fetch(api(`/api/deployment/build-size?jobId=${encodeURIComponent(targetId || '')}&app=${encodeURIComponent(app || '')}&flavor=${encodeURIComponent(flavor || '')}`));
        const data = await res.json();
        if (data.success && data.buildSize) {
            currentBuildSizeInfo = data.buildSize;
            openBuildSizeModal(data.buildSize);
        } else {
            showToast(data.error || data.message || 'No build size data found for this run', 'error');
        }
    } catch (err) {
        showToast('Failed to load build size details', 'error');
    }
}

// Wire Event Listeners
if (els.buildSizeBanner) {
    els.buildSizeBanner.addEventListener('click', () => openBuildSizeModal());
}
if (els.closeBuildSizeModalBtn) {
    els.closeBuildSizeModalBtn.addEventListener('click', closeBuildSizeModal);
}
if (els.closeBuildSizeBtn) {
    els.closeBuildSizeBtn.addEventListener('click', closeBuildSizeModal);
}
if (els.buildSizeModalOverlay) {
    els.buildSizeModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.buildSizeModalOverlay) closeBuildSizeModal();
    });
}
if (els.bsTabDiffBtn) {
    els.bsTabDiffBtn.addEventListener('click', () => switchBuildSizeTab('diff'));
}
if (els.bsTabLargestBtn) {
    els.bsTabLargestBtn.addEventListener('click', () => switchBuildSizeTab('largest'));
}

// Window exports
window.checkAndDisplayBuildSize = checkAndDisplayBuildSize;
window.renderBuildSizeBanner = renderBuildSizeBanner;
window.openBuildSizeModal = openBuildSizeModal;
window.closeBuildSizeModal = closeBuildSizeModal;
window.switchBuildSizeTab = switchBuildSizeTab;
window.renderBuildSizeDiffTable = renderBuildSizeDiffTable;
window.renderBuildSizeLargestTable = renderBuildSizeLargestTable;
window.openBuildSizeModalForTarget = openBuildSizeModalForTarget;
