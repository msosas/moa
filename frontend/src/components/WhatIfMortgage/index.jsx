import { useEffect, useState } from 'react';
import { useWhatIfMortgage } from '../../hooks/useWhatIfMortgage.js';

const fmtMoney = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const fmtPct = (v) => `${(Number(v) * 100).toFixed(2)}%`;

export default function WhatIfMortgage({ profile, baseMortgageStep, narrative }) {
  const [override, setOverride] = useState({
    principal: profile.mortgage?.balance ?? 0,
    term_years: profile.mortgage?.term_years_remaining ?? 25,
  });
  const { data, loading, error, fetchDebounced, reset } = useWhatIfMortgage();

  useEffect(() => {
    reset();
    setOverride({
      principal: profile.mortgage?.balance ?? 0,
      term_years: profile.mortgage?.term_years_remaining ?? 25,
    });
  }, [profile, reset]);

  if (!profile.mortgage || !baseMortgageStep) return null;

  function update(field, value) {
    const next = { ...override, [field]: value };
    setOverride(next);
    fetchDebounced({
      profile,
      override: {
        principal: Number(next.principal),
        term_years: Number(next.term_years),
      },
    }, narrative);
  }

  const alteredStep = data?.plan?.steps?.find((s) => s.kind === 'mortgage_vs_invest');
  const baseInterest = baseMortgageStep.expected_outcome.best_strategy_total_interest;
  const newInterest = alteredStep?.expected_outcome.best_strategy_total_interest;
  const deltaInterest = newInterest != null ? newInterest - baseInterest : null;
  const baseMonthly = baseMortgageStep.expected_outcome.best_strategy_monthly_payment;
  const newMonthly = alteredStep?.expected_outcome.best_strategy_monthly_payment;
  const deltaMonthly = newMonthly != null ? newMonthly - baseMonthly : null;

  return (
    <div className="card p-5 space-y-4">
      <div>
        <div className="font-semibold">What if your mortgage looked different?</div>
        <div className="text-xs text-slate-500 mt-1">
          Adjust the principal or remaining term — the advisor recomputes the mortgage step against your full picture.
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Principal (NZD)</label>
          <input
            type="number" min="0" className="input"
            value={override.principal}
            onChange={(e) => update('principal', e.target.value)}
          />
        </div>
        <div>
          <label className="label">Years remaining</label>
          <input
            type="number" min="1" max="40" className="input"
            value={override.term_years}
            onChange={(e) => update('term_years', e.target.value)}
          />
        </div>
      </div>

      <div className="text-xs text-slate-500">
        Base: {fmtMoney(profile.mortgage.balance)} over {profile.mortgage.term_years_remaining}y at {fmtPct(profile.mortgage.annual_rate)}.
      </div>

      {loading && <div className="text-xs text-slate-400">Recomputing…</div>}
      {error && <div className="text-xs text-risk">{String(error.message || error)}</div>}

      {alteredStep && deltaInterest != null && (
        <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800/60">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">Total interest</div>
            <div className="tabular-nums text-slate-200">{fmtMoney(newInterest)}</div>
            <div className={`text-xs tabular-nums ${deltaInterest > 0 ? 'text-risk' : 'text-emerald-400'}`}>
              {deltaInterest > 0 ? '+' : ''}{fmtMoney(deltaInterest)} vs base
            </div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">Monthly payment</div>
            <div className="tabular-nums text-slate-200">{fmtMoney(newMonthly)}</div>
            <div className={`text-xs tabular-nums ${deltaMonthly > 0 ? 'text-risk' : 'text-emerald-400'}`}>
              {deltaMonthly > 0 ? '+' : ''}{fmtMoney(deltaMonthly)} vs base
            </div>
          </div>
          <div className="col-span-2 text-sm text-slate-300">
            {alteredStep.action}
          </div>
        </div>
      )}
    </div>
  );
}
