import { useState } from 'react';
import PlanStepMath from './PlanStepMath.jsx';

const BAND_STYLES = {
  must_do:      { border: 'border-l-risk',     pill: 'bg-risk/15 text-risk',           label: 'DO THIS FIRST' },
  recommended:  { border: 'border-l-amber-400', pill: 'bg-amber-400/15 text-amber-300', label: 'RECOMMENDED' },
  optional:     { border: 'border-l-emerald-500', pill: 'bg-emerald-500/15 text-emerald-300', label: 'NICE TO HAVE' },
};

const fmtMoney = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function PlanStepCard({ step, index, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const style = BAND_STYLES[step.band] || BAND_STYLES.optional;

  return (
    <div className={`card border-l-4 ${style.border} overflow-hidden`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left px-5 py-4 hover:bg-slate-900/30 transition"
      >
        <div className="flex items-center gap-3 mb-2">
          <span className={`text-[10px] font-bold tracking-wider px-2 py-0.5 rounded ${style.pill}`}>
            {style.label}
          </span>
          <span className="text-xs uppercase tracking-wide text-slate-500">Step {index}</span>
          {(step.amount_today > 0 || step.monthly_amount > 0) && (
            <span className="text-xs text-slate-500 ml-auto tabular-nums">
              {step.amount_today > 0 && <span>{fmtMoney(step.amount_today)} today</span>}
              {step.amount_today > 0 && step.monthly_amount > 0 && <span> · </span>}
              {step.monthly_amount > 0 && <span>{fmtMoney(step.monthly_amount)}/mo</span>}
            </span>
          )}
        </div>
        <div className="text-slate-100">{step.action}</div>
      </button>

      <div className={`px-5 pb-5 space-y-3 text-sm ${open ? '' : 'hidden print:block'}`}>
        <div className="text-slate-300 leading-relaxed">{step.rationale?.primary_reason}</div>
        {(() => {
          const fixedRef = step.references?.find((r) => r.startsWith('fixed_until:'));
          if (!fixedRef) return null;
          return (
            <div className="text-xs text-slate-400">
              Your current fixed term ends on <span className="text-slate-200">{fixedRef.slice('fixed_until:'.length)}</span>.
            </div>
          );
        })()}
        <PlanStepMath
          expectedOutcome={step.expected_outcome}
          rationale={step.rationale}
        />
        {step.suggested_providers && step.suggested_providers.length > 0 && (
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">Where to put it</div>
            <ul className="space-y-1">
              {step.suggested_providers.map((p, i) => (
                <li key={`${p.name}-${i}`} className="text-sm">
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noreferrer" className="text-accent hover:underline font-medium">
                      {p.name}
                    </a>
                  ) : (
                    <span className="text-slate-200 font-medium">{p.name}</span>
                  )}
                  <span className="text-slate-400"> — {p.why}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
