import { useCallback, useRef, useState } from 'react';
import { api } from '../api/client.js';

const DEBOUNCE_MS = 300;

function cacheKey(payload, narrative) {
  // Cached by override + narrative config — switching models invalidates.
  return JSON.stringify({ override: payload.override || {}, narrative: narrative || {} });
}

export function useWhatIfMortgage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const cacheRef = useRef(new Map());
  const timerRef = useRef(null);
  const reqIdRef = useRef(0);

  const fetchOverride = useCallback(async (payload, narrative) => {
    const key = cacheKey(payload, narrative);
    const cached = cacheRef.current.get(key);
    if (cached) {
      setData(cached);
      return cached;
    }
    const id = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await api.whatIfMortgage(payload, narrative);
      cacheRef.current.set(key, result);
      if (id === reqIdRef.current) setData(result);
      return result;
    } catch (e) {
      if (id === reqIdRef.current) setError(e);
      throw e;
    } finally {
      if (id === reqIdRef.current) setLoading(false);
    }
  }, []);

  const fetchDebounced = useCallback((payload, narrative) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      fetchOverride(payload, narrative).catch(() => {});
    }, DEBOUNCE_MS);
  }, [fetchOverride]);

  const reset = useCallback(() => {
    cacheRef.current.clear();
    setData(null);
    setError(null);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return { data, error, loading, fetchDebounced, fetchNow: fetchOverride, reset };
}
