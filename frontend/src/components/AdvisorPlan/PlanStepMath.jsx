const FACT_LABELS = {
  starter_ef_target: 'Target buffer',
  months_to_full_starter: 'Months to fill',
  total_high_interest_balance: 'Total to pay off',
  remaining_after_lump: 'Left after lump-sum hit',
  payoff_months: 'Months to clear',
  extra_employee_monthly: 'Extra from your pay',
  employer_monthly_unlocked: 'Employer adds',
  annual_free_money: 'Total per year (you + employer)',
  target: 'Target',
  months_to_target: 'Months to reach',
  current_monthly_payment: 'You pay today',
  new_minimum_payment: 'New minimum payment',
  extra_per_month: 'Extra we recommend',
  total_monthly_payment: 'Total recommended (minimum + extra)',
  change_vs_current: 'Change vs today',
  best_strategy_total_interest: 'Total interest over the loan',
  best_strategy_monthly_payment: 'Monthly payment (best option)',
  sensitivity_minus_1pct: 'If floating rate falls 1%',
  sensitivity_plus_1pct: 'If floating rate rises 1%',
  ks_after_pie_return: 'What you keep in KiwiSaver (after tax)',
  taxable_after_rwt_return: 'What you keep investing yourself (after tax)',
  new_employee_rate: 'New contribution %',
  td_amount: 'Term deposit (today)',
  idx_amount: 'Share fund (today)',
  td_monthly: 'Term deposit / month',
  idx_monthly: 'Share fund / month',
  projected_at_horizon: 'Estimated value at your horizon',
};

const PCT_KEYS = new Set(['new_employee_rate', 'ks_after_pie_return', 'taxable_after_rwt_return']);
const COUNT_KEYS = new Set(['months_to_full_starter', 'months_to_target', 'payoff_months']);

const fmtMoney = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const fmtPct = (v) => `${(Number(v) * 100).toFixed(2)}%`;
const fmtCount = (v) => Number(v).toFixed(0);

function fmt(key, value) {
  if (value == null) return '—';
  if (PCT_KEYS.has(key)) return fmtPct(value);
  if (COUNT_KEYS.has(key)) return fmtCount(value);
  return fmtMoney(value);
}

export default function PlanStepMath({ expectedOutcome, rationale }) {
  const entries = Object.entries(expectedOutcome || {}).filter(([, v]) => v != null);
  const facts = Object.entries(rationale?.numeric_facts || {});

  if (entries.length === 0 && facts.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
      {entries.map(([k, v]) => (
        <div key={k} className="flex justify-between">
          <span className="text-slate-500">{FACT_LABELS[k] || k}</span>
          <span className="text-slate-200 tabular-nums">{fmt(k, v)}</span>
        </div>
      ))}
    </div>
  );
}
