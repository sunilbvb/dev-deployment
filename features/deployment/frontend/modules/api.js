export function api(path) {
    return (typeof window.apiUrl === 'function') ? window.apiUrl(path) : path;
}

export function fetchWithAuth(url, options = {}) {
    options = options || {};
    const headers = new Headers(options.headers || {});
    if (typeof window !== 'undefined' && window.__DEPLOYMENT_TOKEN__ && !headers.has('X-API-Token')) {
        headers.set('X-API-Token', window.__DEPLOYMENT_TOKEN__);
    }
    options.headers = headers;
    return fetch(url, options);
}
