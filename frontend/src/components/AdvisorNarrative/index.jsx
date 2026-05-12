import Term from '../Term.jsx';
import { renderNarrative } from './autoTermWrap.jsx';

export default function AdvisorNarrative({ text, source }) {
  if (!text) return null;
  const isFallback = source === 'fallback';
  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-semibold">
          A
        </div>
        <div className="text-xs uppercase tracking-wide text-slate-400">Advisor</div>
      </div>
      {isFallback && (
        <div className="text-xs text-amber-400/80 border border-amber-500/30 bg-amber-500/5 rounded px-3 py-2">
          Standard recommendation — the live advisor narrative is offline right now, but the numbers are the same.
        </div>
      )}
      <div className="leading-relaxed text-slate-200 text-sm">
        {renderNarrative(text, Term)}
      </div>
    </div>
  );
}
