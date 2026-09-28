export function api(path) {
    return (typeof window.apiUrl === 'function') ? window.apiUrl(path) : path;
}
