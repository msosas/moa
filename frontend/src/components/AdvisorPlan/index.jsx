import AdvisorNarrative from '../AdvisorNarrative/index.jsx';
import WhatIfMortgage from '../WhatIfMortgage/index.jsx';
import PlanStepCard from './PlanStepCard.jsx';

const fmtMoney = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const fmtPct = (v) => `${(Number(v) * 100).toFixed(1)}%`;

export default function AdvisorPlan({ response, profile, narrativeConfig }) {
  if (!response) return null;
  const { plan, narrative, narrative_source } = response;
  const mortgageStep = plan.steps.find((s) => s.kind === 'mortgage_vs_invest');
  const today = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div className="space-y-5">
      {/* Screen-only header row: section title + actions */}
      <div className="flex items-center justify-between print:hidden">
        <h2 className="text-lg font-semibold">Here's what I'd do</h2>
        <button type="button" onClick={() => window.print()} className="btn-ghost text-sm">
          Download PDF
        </button>
      </div>

      {/* Print-only report header */}
      <div className="hidden print:block">
        <div className="text-2xl font-bold">FinPath AI — Your plan</div>
        <div className="text-xs text-slate-500">Generated {today}</div>
      </div>

      <AdvisorNarrative text={narrative} source={narrative_source} />

      <div className="grid grid-cols-3 gap-3 text-center">
        <Tile label="Take-home / mo"  value={fmtMoney(plan.cash_flow.net_monthly_income)} />
        <Tile label="Monthly surplus" value={fmtMoney(plan.cash_flow.monthly_surplus)} highlight />
        <Tile label="Savings rate"    value={fmtPct(plan.cash_flow.savings_rate)} />
      </div>

      <div className="space-y-3">
        {plan.steps.map((step, i) => (
          <PlanStepCard
            key={step.id}
            step={step}
            index={i + 1}
            defaultOpen={i === 0}
          />
        ))}
      </div>

      {mortgageStep && (
        <div className="print:hidden">
          <WhatIfMortgage profile={profile} baseMortgageStep={mortgageStep} narrative={narrativeConfig} />
        </div>
      )}

      <HorizonTable horizon={plan.horizon_projection} years={profile.time_horizon_years} />
    </div>
  );
}

function Tile({ label, value, highlight }) {
  return (
    <div className={`p-3 bg-slate-900/40 border rounded-lg ${highlight ? 'border-accent/40' : 'border-slate-800'}`}>
      <div className="text-xs text-slate-400 uppercase tracking-wide">{label}</div>
      <div className={`text-xl font-semibold tabular-nums mt-1 ${highlight ? 'text-accent' : ''}`}>{value}</div>
    </div>
  );
}

function HorizonTable({ horizon, years }) {
  return (
    <div className="card p-5">
      <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">
        Projected net worth at {years}-year horizon
      </div>
      <div className="grid grid-cols-2 gap-y-1 text-sm">
        <Row label="Emergency fund"      value={horizon.emergency_fund} />
        <Row label="KiwiSaver"           value={horizon.kiwisaver} />
        <Row label="Taxable investments" value={horizon.taxable_investments} />
        <Row label="Mortgage remaining"  value={horizon.debt_remaining} negative />
        <div className="col-span-2 border-t border-slate-800/60 mt-2 pt-2 flex justify-between">
          <span className="text-slate-200 font-medium">Total net worth</span>
          <span className="text-slate-100 tabular-nums font-semibold">{fmtMoney(horizon.total_net_worth)}</span>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, negative }) {
  return (
    <>
      <span className="text-slate-400">{label}</span>
      <span className={`tabular-nums text-right ${negative ? 'text-risk' : 'text-slate-200'}`}>
        {negative ? '−' : ''}{fmtMoney(Math.abs(value))}
      </span>
    </>
  );
}
