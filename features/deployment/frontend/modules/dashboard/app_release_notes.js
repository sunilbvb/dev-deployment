/**
 * app_release_notes.js — optional, multi-language release notes.
 *
 * One editor component used in two places:
 *   - inline in the Run panel (notes ride along with the run, never a confirmation)
 *   - the History "Release notes" dialog (view / add / edit notes of a finished build)
 * Languages are set per app and can be read from the store listing.
 */

function rnEsc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function rnRequest(path, body) {
    const opts = body === undefined ? {} : {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    };
    const res = await fetch(api(path), opts);
    return res.json();
}

function rnToast(message) {
    if (typeof showToast === 'function') showToast(message);
}

/**
 * createNotesEditor(root, {app, platform, version})
 * -> { load(version), getNotes(), setVersion(v), identifier() }
 */
function createNotesEditor(root, opts) {
    const st = {
        app: opts.app, platform: opts.platform, version: opts.version || '',
        locales: [], active: '', texts: {}, limit: 500,
        defaults: {}, lastBuild: { version: '', notes: {} },
    };
    root.innerHTML = `
        <div class="rn-locales" style="display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-bottom:6px;"></div>
        <textarea class="ui-input rn-text" rows="4" placeholder="Release notes (optional) — leave empty to ship without" style="width:100%; resize:vertical;"></textarea>
        <div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:6px; font-size:0.76rem;">
            <span class="rn-count" style="font-family:monospace;"></span>
            <button type="button" class="ui-button rn-last" data-variant="ghost" data-size="xs">Use last build's notes</button>
            <button type="button" class="ui-button rn-clear" data-variant="ghost" data-size="xs">Clear</button>
            <span style="margin-left:auto; display:flex; gap:6px; align-items:center;">
                <input class="ui-input rn-add" placeholder="add language e.g. de-DE" style="width:150px; font-size:0.76rem;">
                <button type="button" class="ui-button rn-add-btn" data-variant="ghost" data-size="xs">Add</button>
                <button type="button" class="ui-button rn-store" data-variant="ghost" data-size="xs" title="Read the languages already set up in the store listing">Languages from store</button>
            </span>
        </div>`;
    const q = sel => root.querySelector(sel);
    const textarea = q('.rn-text');

    function remember() { if (st.active) st.texts[st.active] = textarea.value; }

    function renderLocales() {
        q('.rn-locales').innerHTML = st.locales.map(l => `
            <button type="button" class="ui-button rn-loc" data-loc="${rnEsc(l)}" data-variant="${l === st.active ? 'primary' : 'secondary'}" data-size="xs">
                ${rnEsc(l)}${(st.texts[l] || '').trim() ? ' ●' : ''}
            </button>
            ${st.locales.length > 1 ? `<button type="button" class="rn-del" data-loc="${rnEsc(l)}" title="Remove ${rnEsc(l)} from this app" style="background:none;border:0;cursor:pointer;opacity:.6;margin-left:-4px;">×</button>` : ''}`).join('');
    }

    function renderText() {
        textarea.value = st.texts[st.active] || '';
        const len = textarea.value.length;
        const c = q('.rn-count');
        c.textContent = `${len} / ${st.limit}`;
        c.style.color = len > st.limit ? '#ef4444' : 'var(--ui-text-muted)';
        q('.rn-last').style.display = st.lastBuild.version ? '' : 'none';
        q('.rn-last').textContent = `Use last build's notes (${st.lastBuild.version})`;
    }

    function paint() { renderLocales(); renderText(); }

    async function saveLocales() {
        const res = await rnRequest('/api/deployment/release-notes/locales', { app: st.app, locales: st.locales });
        if (!res.success) rnToast('❌ ' + (res.error || 'Could not save languages'));
    }

    async function load(version) {
        if (version !== undefined) st.version = version;
        if (!st.app) return;
        const data = await rnRequest(`/api/deployment/release-notes?app=${encodeURIComponent(st.app)}&platform=${encodeURIComponent(st.platform)}&version=${encodeURIComponent(st.version)}`);
        if (!data.success) { rnToast('❌ ' + (data.error || 'Could not load release notes')); return; }
        st.locales = data.locales;
        st.limit = data.limit;
        st.lastBuild = data.lastBuild || { version: '', notes: {} };
        st.texts = {};
        data.locales.forEach(l => {
            const n = data.notes[l] || { text: '' };
            // autofill: this build's notes, else the shared default, else the last build's
            st.texts[l] = n.text || (st.lastBuild.notes || {})[l] || '';
        });
        if (!st.locales.includes(st.active)) st.active = st.locales[0] || '';
        paint();
    }

    root.addEventListener('click', async event => {
        const loc = event.target.closest('.rn-loc');
        const del = event.target.closest('.rn-del');
        if (loc) { remember(); st.active = loc.dataset.loc; paint(); return; }
        if (del) {
            remember();
            st.locales = st.locales.filter(l => l !== del.dataset.loc);
            delete st.texts[del.dataset.loc];
            if (st.active === del.dataset.loc) st.active = st.locales[0];
            paint();
            await saveLocales();
            return;
        }
        if (event.target.closest('.rn-clear')) { textarea.value = ''; remember(); paint(); return; }
        if (event.target.closest('.rn-last')) {
            st.locales.forEach(l => { if ((st.lastBuild.notes || {})[l]) st.texts[l] = st.lastBuild.notes[l]; });
            paint();
            return;
        }
        if (event.target.closest('.rn-add-btn')) {
            const input = q('.rn-add');
            const value = input.value.trim().replace('_', '-');
            if (!/^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$/.test(value)) { rnToast('Use a language code like de-DE'); return; }
            remember();
            if (!st.locales.includes(value)) st.locales.push(value);
            st.active = value;
            input.value = '';
            paint();
            await saveLocales();
            return;
        }
        if (event.target.closest('.rn-store')) {
            const btn = event.target.closest('.rn-store');
            const ident = opts.identifier ? opts.identifier() : '';
            btn.disabled = true;
            try {
                const res = await rnRequest(`/api/deployment/release-notes/store-locales?app=${encodeURIComponent(st.app)}&platform=${encodeURIComponent(st.platform)}&identifier=${encodeURIComponent(ident)}`);
                if (!res.success) throw new Error(res.error || 'Could not read store languages');
                if (!res.locales.length) throw new Error('The store listing has no languages yet');
                remember();
                res.locales.forEach(l => { if (!st.locales.includes(l)) st.locales.push(l); });
                st.locales = st.locales.filter(l => res.locales.includes(l) || (st.texts[l] || '').trim());
                if (!st.locales.includes(st.active)) st.active = st.locales[0];
                paint();
                await saveLocales();
                rnToast(`✅ Languages from store: ${res.locales.join(', ')}`);
            } catch (err) {
                rnToast('❌ ' + err.message);
            } finally { btn.disabled = false; }
        }
    });
    textarea.addEventListener('input', () => { remember(); renderText(); renderLocales(); });

    return {
        load,
        setVersion(v) { st.version = v; },
        getNotes() {
            remember();
            const out = {};
            st.locales.forEach(l => { const t = (st.texts[l] || '').trim(); if (t) out[l] = t; });
            return out;
        },
        // Every language incl. empty ones, so a save can clear a language.
        getAllNotes() {
            remember();
            const out = {};
            st.locales.forEach(l => { out[l] = (st.texts[l] || '').trim(); });
            return out;
        },
    };
}

/* ───────────────────────── Run panel (inline, no confirmation) ───────────────────────── */

const runNotes = { editor: null, key: '' };

function commandTakesNotes(cmd) {
    return !!cmd && (cmd.platform === 'android' || cmd.platform === 'ios' || cmd.platform === 'combined')
        && /upload|deploy|release|testflight|store/i.test(String(cmd.templateId || cmd.id || ''));
}

/** Called by updateExecutionPanel(); shows/hides and (re)loads the inline editor. */
function refreshRunNotesPanel() {
    const panel = document.getElementById('runNotesPanel');
    if (!panel) return;
    const cmd = typeof state !== 'undefined' && state.selectedCommand;
    const app = typeof state !== 'undefined' && state.selectedApp;
    if (!app || !commandTakesNotes(cmd) || state.selectedPipeline) {
        panel.classList.add('hidden');
        return;
    }
    panel.classList.remove('hidden');
    const platform = cmd.platform === 'combined' ? 'android' : cmd.platform; // same notes go to both stores
    const key = `${app}|${platform}`;
    if (runNotes.key !== key) {
        runNotes.key = key;
        runNotes.editor = createNotesEditor(document.getElementById('runNotesEditor'), { app, platform });
        runNotes.editor.load('');
    }
}

/** Release notes to send with the run; undefined when the field was left empty. */
function collectRunNotes() {
    const panel = document.getElementById('runNotesPanel');
    if (!panel || panel.classList.contains('hidden') || !runNotes.editor) return undefined;
    const notes = runNotes.editor.getNotes();
    return Object.keys(notes).length ? notes : undefined;
}

/* ───────────────────────── History dialog ───────────────────────── */

const historyNotes = { editor: null, entry: null };

async function openReleaseNotesForHistory(entryId) {
    const entry = (state.historyEntries || []).find(e => e.id === entryId);
    if (!entry) return;
    historyNotes.entry = entry;
    const platform = entry.platform || (/ipa|ios|testflight/i.test(entry.templateId || '') ? 'ios' : 'android');
    const overlay = document.getElementById('releaseNotesOverlay');
    document.getElementById('rnHistoryTitle').textContent = `${entry.app || ''} · ${platform === 'ios' ? 'TestFlight' : 'Google Play'} · ${entry.flavor || ''}`;
    const versionInput = document.getElementById('rnVersionInput');
    versionInput.value = entry.buildNumber || '';
    const identRow = document.getElementById('rnIdentifierRow');
    const identInput = document.getElementById('rnIdentifierInput');
    identInput.value = '';
    try { identInput.value = localStorage.getItem(`rnIdent:${entry.app}:${platform}`) || ''; } catch (e) { /* storage unavailable */ }
    document.getElementById('rnPublishBtn').style.display = platform === 'ios' ? '' : 'none';
    document.getElementById('rnAndroidNote').style.display = platform === 'android' ? '' : 'none';
    identRow.style.display = '';
    overlay.classList.add('ui-active');
    historyNotes.platform = platform;
    historyNotes.editor = createNotesEditor(document.getElementById('rnHistoryEditor'), {
        app: entry.app, platform, version: versionInput.value, identifier: () => identInput.value.trim(),
    });
    if (!identInput.value) {
        try {
            const d = await rnRequest(`/api/deployment/release-notes/identifier?app=${encodeURIComponent(entry.app)}&platform=${platform}&flavor=${encodeURIComponent(entry.flavor || '')}`);
            if (d.identifier) identInput.value = d.identifier;
        } catch (e) { /* user can type it */ }
    }
    await historyNotes.editor.load(versionInput.value);
}

async function saveHistoryNotes(publish) {
    const version = document.getElementById('rnVersionInput').value.trim();
    const ident = document.getElementById('rnIdentifierInput').value.trim();
    const entry = historyNotes.entry;
    if (!version) { rnToast('Enter the build number first.'); return; }
    if (publish && !ident) { rnToast('Enter the Bundle ID to publish to TestFlight.'); return; }
    try { localStorage.setItem(`rnIdent:${entry.app}:${historyNotes.platform}`, ident); } catch (e) { /* storage unavailable */ }
    const btn = document.getElementById(publish ? 'rnPublishBtn' : 'rnSaveBtn');
    btn.disabled = true;
    try {
        const res = await rnRequest(publish ? '/api/deployment/release-notes/publish' : '/api/deployment/release-notes/save', {
            app: entry.app, platform: historyNotes.platform, version, identifier: ident,
            notes: historyNotes.editor.getAllNotes(),
        });
        if (!res.success) throw new Error(res.error || 'Failed');
        rnToast(publish ? `✅ Saved and published to TestFlight build ${version}` : '✅ Release notes saved');
    } catch (err) {
        rnToast('❌ ' + err.message);
    } finally { btn.disabled = false; }
}

document.addEventListener('DOMContentLoaded', () => {
    const close = () => document.getElementById('releaseNotesOverlay')?.classList.remove('ui-active');
    document.getElementById('rnCloseBtn')?.addEventListener('click', close);
    document.getElementById('rnSaveBtn')?.addEventListener('click', () => saveHistoryNotes(false));
    document.getElementById('rnPublishBtn')?.addEventListener('click', () => saveHistoryNotes(true));
    document.getElementById('rnVersionInput')?.addEventListener('change', e => historyNotes.editor && historyNotes.editor.load(e.target.value.trim()));
});
