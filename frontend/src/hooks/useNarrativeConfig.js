import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'moa:narrative_config';
const DEFAULT = { provider: 'ollama', model: null };
const VALID_PROVIDERS = new Set(['ollama', 'templated']);

function read() {
  if (typeof window === 'undefined') return DEFAULT;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT;
    const parsed = JSON.parse(raw);
    const merged = { ...DEFAULT, ...parsed };
    // Drop legacy provider values (e.g. "anthropic") so the UI doesn't render
    // a dropdown stuck on an option that no longer exists.
    if (!VALID_PROVIDERS.has(merged.provider)) {
      return { ...DEFAULT };
    }
    return merged;
  } catch {
    return DEFAULT;
  }
}

export function useNarrativeConfig() {
  const [config, setConfig] = useState(read);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch {
      // ignore quota / disabled storage
    }
  }, [config]);

  const setProvider = useCallback((provider) => {
    setConfig((c) => ({ ...c, provider, model: null }));
  }, []);

  const setModel = useCallback((model) => {
    setConfig((c) => ({ ...c, model }));
  }, []);

  return { config, setProvider, setModel };
}
