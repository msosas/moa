import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client.js';

const PROVIDER_OPTIONS = [
  { id: 'anthropic', label: 'Claude (cloud)' },
  { id: 'ollama',    label: 'Local (Ollama)' },
  { id: 'templated', label: 'No LLM (templated)' },
];

export default function NarrativeSettings({ config, onProviderChange, onModelChange }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchModels = useCallback(async (provider) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.listModels(provider);
      setModels(resp.models || []);
      // Auto-pick first model if none chosen yet and at least one available.
      if (!config.model && resp.models?.length) {
        onModelChange(resp.models[0].id);
      }
      if (config.model && !resp.models.find((m) => m.id === config.model)) {
        // Selected model not in the list (e.g. switched providers) — reset.
        onModelChange(resp.models[0]?.id || null);
      }
    } catch (e) {
      setError(e);
      setModels([]);
    } finally {
      setLoading(false);
    }
  }, [config.model, onModelChange]);

  useEffect(() => {
    fetchModels(config.provider);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.provider]);

  return (
    <div className="card p-4 flex flex-wrap items-center gap-3 text-sm print:hidden">
      <span className="text-xs uppercase tracking-wide text-slate-500">Narrative model</span>

      <select
        value={config.provider}
        onChange={(e) => onProviderChange(e.target.value)}
        className="bg-slate-900/60 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200 focus:outline-none focus:ring-2 focus:ring-accent/60"
      >
        {PROVIDER_OPTIONS.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>

      {config.provider !== 'templated' && (
        <select
          value={config.model || ''}
          onChange={(e) => onModelChange(e.target.value || null)}
          disabled={loading || !models.length}
          className="bg-slate-900/60 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-accent/60 min-w-[180px]"
        >
          {!models.length && <option value="">{loading ? 'Loading…' : 'No models available'}</option>}
          {models.map((m) => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </select>
      )}

      <button
        type="button"
        onClick={() => fetchModels(config.provider)}
        disabled={loading || config.provider === 'templated'}
        className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-50"
        title="Refresh model list"
      >
        ↻ Refresh
      </button>

      {error && (
        <span className="text-xs text-risk">Couldn't reach {config.provider}.</span>
      )}
      {!loading && !error && !models.length && config.provider === 'ollama' && (
        <span className="text-xs text-amber-400/80">
          Ollama unreachable — start it on the host (or check OLLAMA_BASE_URL).
        </span>
      )}
      {!loading && !error && !models.length && config.provider === 'anthropic' && (
        <span className="text-xs text-amber-400/80">
          No Anthropic key configured.
        </span>
      )}
    </div>
  );
}
