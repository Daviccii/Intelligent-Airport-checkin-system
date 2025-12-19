(function () {
  function normalizeBase(url) {
    try {
      if (!url) return '';
      const u = new URL(url);
      return u.origin; // strips path and trailing slash
    } catch {
      return '';
    }
  }

  const candidates = [];
  const stored = localStorage.getItem('adminApiBase');
  if (stored) candidates.push(stored);
  if (location && location.protocol && location.protocol.startsWith('http')) {
    candidates.push(location.origin);
  }
  candidates.push('http://127.0.0.1:8000');
  candidates.push('http://127.0.0.1:5000');

  let base = '';
  for (const c of candidates) {
    const n = normalizeBase(c);
    if (n) { base = n; break; }
  }

  function buildUrl(path) {
    if (!path) return base;
    if (/^https?:\/\//i.test(path)) return path;
    const p = path.startsWith('/') ? path : '/' + path;
    return base + p;
  }

  window.getApiBase = function () { return base; };
  window.setApiBase = function (url) {
    const n = normalizeBase(url);
    if (n) {
      base = n;
      localStorage.setItem('adminApiBase', n);
    }
  };

  window.apiFetch = function (path, options) {
    const url = buildUrl(path);
    return fetch(url, options);
  };
})();
