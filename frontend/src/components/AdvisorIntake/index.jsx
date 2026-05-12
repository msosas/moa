import { useMemo, useState } from 'react';
import Term from '../Term.jsx';
import IntakeSection from './IntakeSection.jsx';
import IntakeField from './IntakeField.jsx';
import FrequencyInput from './FrequencyInput.jsx';
import RiskSlider from './RiskSlider.jsx';
import DebtRepeater from './DebtRepeater.jsx';
import KiwiSaverBlock from './KiwiSaverBlock.jsx';

const fmtMoney = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const TO_MONTHLY = { weekly: 52 / 12, fortnightly: 26 / 12, monthly: 1, annual: 1 / 12 };

function toMonthly({ value, frequency }) {
  return Number(value || 0) * (TO_MONTHLY[frequency] ?? 1);
}

const STABILITY_OPTIONS = [
  ['stable', 'Stable salary'],
  ['moderate', 'Mostly steady'],
  ['unstable', 'Variable / contract'],
];

const GOAL_OPTIONS = [
  ['build_wealth', 'Build long-term wealth'],
  ['buy_first_home', 'Buy a home'],
  ['pay_off_debt_faster', 'Pay off debt faster'],
  ['retire_comfortably', 'Retire comfortably'],
  ['save_for_kids', 'Save for kids'],
];

const DEFAULT_FORM = {
  age: 35,
  dependents: 0,
  job_stability: 'moderate',
  time_horizon_years: 10,
  risk_tolerance: 'medium',

  income: { value: 80_000, frequency: 'annual' },
  expenses: { value: 3_500, frequency: 'monthly' },

  has_mortgage: false,
  mortgage: {
    balance: 500_000,
    rate_pct: 5.35,
    term_years_remaining: 25,
    current_strategy: 'fixed_2y',
    monthly_payment: '',         // optional — backend derives from balance/rate/term if blank
    fixed_until: '',             // optional ISO date (YYYY-MM-DD)
  },

  debts: [],

  has_kiwisaver: true,
  kiwisaver: { balance: 25_000, employee_rate: 0.03, employer_rate: 0.03, pir: 0.28, fund_type: 'balanced' },

  current_emergency_fund: 0,
  lump_sum_available: 0,
  existing_investments_amount: 0,

  goals: ['build_wealth'],
  narration_style: 'detailed',
};

const STRATEGY_OPTIONS = [
  ['fixed_1y', '1-year fixed'],
  ['fixed_2y', '2-year fixed'],
  ['fixed_3y', '3-year fixed'],
  ['fixed_5y', '5-year fixed'],
  ['floating', 'Floating'],
];

function formToProfile(form) {
  const incomes = [{
    label: 'Salary',
    gross_amount: Number(form.income.value),
    frequency: form.income.frequency,
  }];
  const expenses = [{
    category: 'other',
    amount: Number(form.expenses.value),
    frequency: form.expenses.frequency,
  }];
  const debts = form.debts
    .filter((d) => Number(d.balance) > 0)
    .map((d) => ({
      kind: d.kind,
      balance: Number(d.balance),
      annual_rate: Number(d.rate_pct) / 100,
    }));
  const mortgage = form.has_mortgage ? {
    balance: Number(form.mortgage.balance),
    annual_rate: Number(form.mortgage.rate_pct) / 100,
    term_years_remaining: Number(form.mortgage.term_years_remaining),
    current_strategy: form.mortgage.current_strategy || null,
    monthly_payment: form.mortgage.monthly_payment ? Number(form.mortgage.monthly_payment) : null,
    fixed_until: form.mortgage.fixed_until || null,
  } : null;
  const kiwisaver = form.has_kiwisaver ? {
    balance: Number(form.kiwisaver.balance),
    employee_rate: Number(form.kiwisaver.employee_rate),
    employer_rate: Number(form.kiwisaver.employer_rate),
    pir: Number(form.kiwisaver.pir),
    fund_type: form.kiwisaver.fund_type,
  } : null;
  const existing_investments = Number(form.existing_investments_amount) > 0
    ? [{ label: 'Investments', vehicle: 'index_fund', balance: Number(form.existing_investments_amount) }]
    : [];

  return {
    age: Number(form.age),
    dependents: Number(form.dependents),
    job_stability: form.job_stability,
    time_horizon_years: Number(form.time_horizon_years),
    risk_tolerance: form.risk_tolerance,
    incomes,
    expenses,
    debts,
    mortgage,
    kiwisaver,
    existing_investments,
    current_emergency_fund: Number(form.current_emergency_fund),
    lump_sum_available: Number(form.lump_sum_available),
    goals: form.goals.length ? form.goals : ['general_review'],
    narration_style: form.narration_style,
  };
}

export default function AdvisorIntake({ onSubmit, loading, error }) {
  const [form, setForm] = useState(DEFAULT_FORM);

  const monthlyIncome = useMemo(() => toMonthly(form.income), [form.income]);
  const monthlyExpenses = useMemo(() => toMonthly(form.expenses), [form.expenses]);
  const monthlySurplus = Math.max(0, monthlyIncome - monthlyExpenses);

  function patch(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }
  function patchNested(field, subpatch) {
    setForm((f) => ({ ...f, [field]: { ...f[field], ...subpatch } }));
  }
  function toggleGoal(goal) {
    setForm((f) => {
      const has = f.goals.includes(goal);
      return { ...f, goals: has ? f.goals.filter((g) => g !== goal) : [...f.goals, goal] };
    });
  }

  function submit(e) {
    e.preventDefault();
    onSubmit(formToProfile(form));
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <IntakeSection title="About you" defaultOpen>
        <div className="grid grid-cols-2 gap-4">
          <IntakeField label="Age" helper="Roughly is fine.">
            <input
              type="number" min="16" max="100" className="input"
              value={form.age} onChange={(e) => patch('age', e.target.value)}
            />
          </IntakeField>
          <IntakeField label="Dependents" helper="Anyone financially relying on you.">
            <input
              type="number" min="0" max="10" className="input"
              value={form.dependents} onChange={(e) => patch('dependents', e.target.value)}
            />
          </IntakeField>
          <IntakeField label="Income stability">
            <select
              className="input"
              value={form.job_stability}
              onChange={(e) => patch('job_stability', e.target.value)}
            >
              {STABILITY_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>{label}</option>
              ))}
            </select>
          </IntakeField>
          <IntakeField
            label={<><Term id="horizon">Time horizon</Term> (years)</>}
            helper="How long until you'd want this money."
          >
            <input
              type="number" min="1" max="40" className="input"
              value={form.time_horizon_years}
              onChange={(e) => patch('time_horizon_years', e.target.value)}
            />
          </IntakeField>
          <div className="col-span-2">
            <label className="label"><Term id="risk-profile">Risk tolerance</Term></label>
            <RiskSlider value={form.risk_tolerance} onChange={(v) => patch('risk_tolerance', v)} />
          </div>
        </div>
      </IntakeSection>

      <IntakeSection
        title="Income & expenses"
        summary={`${fmtMoney(monthlyIncome)}/mo income · ${fmtMoney(monthlyExpenses)}/mo expenses`}
      >
        <IntakeField
          label="Gross income (before tax)"
          helper="We'll compute PAYE + ACC ourselves to figure out your take-home."
        >
          <FrequencyInput
            value={form.income.value}
            frequency={form.income.frequency}
            onChange={(next) => patch('income', next)}
          />
        </IntakeField>
        <IntakeField
          label="Living expenses"
          helper={`≈ ${fmtMoney(monthlyExpenses)} / month`}
        >
          <FrequencyInput
            value={form.expenses.value}
            frequency={form.expenses.frequency}
            onChange={(next) => patch('expenses', next)}
            frequencies={['weekly', 'fortnightly', 'monthly']}
          />
        </IntakeField>
        <div className="text-sm text-slate-400">
          Estimated monthly surplus: <span className="text-slate-200">{fmtMoney(monthlySurplus)}</span>
          <span className="text-xs"> (gross income net of PAYE/ACC is computed server-side)</span>
        </div>
      </IntakeSection>

      <IntakeSection
        title="Debts & mortgage"
        summary={form.has_mortgage || form.debts.length > 0
          ? `${form.has_mortgage ? `${fmtMoney(form.mortgage.balance)} mortgage` : 'No mortgage'} · ${form.debts.length} other debt${form.debts.length === 1 ? '' : 's'}`
          : 'No debts'}
      >
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={form.has_mortgage}
            onChange={(e) => patch('has_mortgage', e.target.checked)}
            className="accent-emerald-500"
          />
          <span>I have a <Term id="mortgage-spread">mortgage</Term></span>
        </label>

        {form.has_mortgage && (
          <div className="grid grid-cols-2 gap-3 pt-1">
            <IntakeField label="Balance (NZD)">
              <input
                type="number" min="0" className="input"
                value={form.mortgage.balance}
                onChange={(e) => patchNested('mortgage', { balance: e.target.value })}
              />
            </IntakeField>
            <IntakeField label="Current rate (% per year)">
              <input
                type="number" min="0" step="0.01" className="input"
                value={form.mortgage.rate_pct}
                onChange={(e) => patchNested('mortgage', { rate_pct: e.target.value })}
              />
            </IntakeField>
            <IntakeField label="Years remaining">
              <input
                type="number" min="1" max="40" className="input"
                value={form.mortgage.term_years_remaining}
                onChange={(e) => patchNested('mortgage', { term_years_remaining: e.target.value })}
              />
            </IntakeField>
            <IntakeField label="Current strategy">
              <select
                className="input"
                value={form.mortgage.current_strategy}
                onChange={(e) => patchNested('mortgage', { current_strategy: e.target.value })}
              >
                {STRATEGY_OPTIONS.map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
            </IntakeField>
            <IntakeField
              label="Current monthly payment (NZD)"
              helper="Leave blank — we'll work it out from your balance, rate, and term."
            >
              <input
                type="number" min="0" step="1" className="input"
                placeholder="auto"
                value={form.mortgage.monthly_payment}
                onChange={(e) => patchNested('mortgage', { monthly_payment: e.target.value })}
              />
            </IntakeField>
            <IntakeField
              label="Fixed term ends on"
              helper="The date your current fix expires. Skip if you're on a floating rate."
            >
              <input
                type="date" className="input"
                value={form.mortgage.fixed_until}
                onChange={(e) => patchNested('mortgage', { fixed_until: e.target.value })}
              />
            </IntakeField>
          </div>
        )}

        <div className="pt-2">
          <div className="label">Other debts</div>
          <DebtRepeater rows={form.debts} onChange={(rows) => patch('debts', rows)} />
        </div>
      </IntakeSection>

      <IntakeSection
        title="Savings, investments & KiwiSaver"
        summary={form.has_kiwisaver
          ? `KiwiSaver at ${(form.kiwisaver.employee_rate * 100).toFixed(0)}% · ${fmtMoney(form.kiwisaver.balance)}`
          : 'No KiwiSaver'}
      >
        <div className="grid grid-cols-2 gap-3">
          <IntakeField
            label="Cash savings (NZD)"
            helper="Money in your bank account today that isn't your emergency fund — we'll decide what to do with it."
          >
            <input
              type="number" min="0" className="input"
              value={form.lump_sum_available}
              onChange={(e) => patch('lump_sum_available', e.target.value)}
            />
          </IntakeField>
          <IntakeField
            label="Current emergency fund"
            helper="Cash you've already set aside as a safety buffer."
          >
            <input
              type="number" min="0" className="input"
              value={form.current_emergency_fund}
              onChange={(e) => patch('current_emergency_fund', e.target.value)}
            />
          </IntakeField>
          <IntakeField
            label="Other investments (total NZD)"
            helper="Already invested — index funds, shares, term deposits, etc. (Excludes KiwiSaver.)"
          >
            <input
              type="number" min="0" className="input"
              value={form.existing_investments_amount}
              onChange={(e) => patch('existing_investments_amount', e.target.value)}
            />
          </IntakeField>
        </div>

        <KiwiSaverBlock
          value={form.kiwisaver}
          onChange={(next) => patch('kiwisaver', next)}
          enabled={form.has_kiwisaver}
          onToggle={(v) => patch('has_kiwisaver', v)}
        />
      </IntakeSection>

      <IntakeSection title="What you want to do" summary={`${form.goals.length} goal${form.goals.length === 1 ? '' : 's'}`}>
        <div>
          <div className="label">Goals (select any that apply)</div>
          <div className="flex flex-wrap gap-2">
            {GOAL_OPTIONS.map(([id, label]) => {
              const on = form.goals.includes(id);
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => toggleGoal(id)}
                  className={`px-3 py-1.5 rounded-full text-sm border transition ${
                    on
                      ? 'bg-accent/15 border-accent/60 text-accent'
                      : 'bg-slate-900/40 border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
        <div>
          <div className="label">Response style</div>
          <div className="flex gap-2">
            {['brief', 'detailed'].map((style) => (
              <label key={style} className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="radio" name="narration_style" value={style}
                  checked={form.narration_style === style}
                  onChange={() => patch('narration_style', style)}
                  className="accent-emerald-500"
                />
                <span className="capitalize text-slate-200">{style}</span>
              </label>
            ))}
          </div>
        </div>
      </IntakeSection>

      <div className="pt-2">
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? 'Building your plan…' : 'Build my plan'}
        </button>
        {error && <div className="text-risk text-sm mt-2">{String(error.message || error)}</div>}
      </div>
    </form>
  );
}
