import { useState } from 'react';
import { api } from '../api/client.js';

export function useAdvisorPlan() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function submit(profile, narrative) {
    setLoading(true);
    setError(null);
    try {
      const result = await api.advisorPlan(profile, narrative);
      setData(result);
      return result;
    } catch (e) {
      setError(e);
      throw e;
    } finally {
      setLoading(false);
    }
  }

  return { data, error, loading, submit };
}
