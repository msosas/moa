// If VITE_API_BASE_URL is set at build time, use it. Otherwise pick a sensible
// default at runtime:
//   - On a standard port (no port, 80, 443) — implying a reverse proxy fronts
//     the app — use a same-origin relative URL so the proxy can route /api/*
//     to the backend.
//   - On a non-standard port (typical dev: 5173) — hit ":8000" on the same
//     hostname. Works for direct localhost dev and cross-LAN dev.
function defaultBase() {
  if (typeof window === 'undefined') return 'http://localhost:8000';
  const { protocol, hostname, port } = window.location;
  const isStandardPort = port === '' || port === '80' || port === '443';
  if (isStandardPort) return '';   // same-origin relative
  return `${protocol}//${hostname}:8000`;
}

const BASE = (import.meta.env.VITE_API_BASE_URL || defaultBase()).replace(/\/$/, '');

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${method} ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

function withNarrativeQuery(path, narrative) {
  if (!narrative || !narrative.provider) return path;
  const qs = new URLSearchParams();
  qs.set('narrative_provider', narrative.provider);
  if (narrative.model) qs.set('narrative_model', narrative.model);
  return `${path}?${qs.toString()}`;
}

export const api = {
  rates: () => request('/api/rates'),
  advisorPlan: (profile, narrative) =>
    request(withNarrativeQuery('/api/advisor/plan', narrative), { method: 'POST', body: profile }),
  whatIfMortgage: (payload, narrative) =>
    request(withNarrativeQuery('/api/advisor/whatif/mortgage', narrative), { method: 'POST', body: payload }),
  listModels: (provider) =>
    request(`/api/advisor/models?provider=${encodeURIComponent(provider)}`),
};
