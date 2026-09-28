export function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

export function showToast(message, toastEl) {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.classList.remove('hidden');
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => toastEl.classList.add('hidden'), 2400);
}

export function prettyCommandTitle(commandKey) {
    const key = String(commandKey || '');
    return key.split('-').filter(Boolean).map(part => {
        const lower = part.toLowerCase();
        if (lower === 'dev') return 'DEV';
        if (lower === 'qa' || lower === 'test') return 'QA';
        if (lower === 'prod') return 'PROD';
        if (lower === 'ipa') return 'IPA';
        if (lower === 'aab') return 'AAB';
        if (lower === 'apk') return 'APK';
        if (lower === 'ios') return 'iOS';
        return lower.charAt(0).toUpperCase() + lower.slice(1);
    }).join(' ');
}
