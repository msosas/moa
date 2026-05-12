import Term from '../Term.jsx';
import IntakeField from './IntakeField.jsx';

const EMPLOYEE_RATES = [0.03, 0.04, 0.06, 0.08, 0.10];
const PIR_OPTIONS = [
  { value: 0.105, label: '10.5%' },
  { value: 0.175, label: '17.5%' },
  { value: 0.28,  label: '28% (most adults)' },
];

export default function KiwiSaverBlock({ value, onChange, enabled, onToggle }) {
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          className="accent-emerald-500"
        />
        <span>I'm enrolled in <Term id="kiwisaver">KiwiSaver</Term></span>
      </label>

      {enabled && (
        <div className="grid grid-cols-2 gap-3 pt-1">
          <IntakeField label="Current balance (NZD)">
            <input
              type="number"
              min="0"
              className="input"
              value={value.balance}
              onChange={(e) => onChange({ ...value, balance: e.target.value })}
            />
          </IntakeField>

          <IntakeField label="Your contribution %">
            <select
              className="input"
              value={value.employee_rate}
              onChange={(e) => onChange({ ...value, employee_rate: parseFloat(e.target.value) })}
            >
              {EMPLOYEE_RATES.map((r) => (
                <option key={r} value={r}>{(r * 100).toFixed(0)}%</option>
              ))}
            </select>
          </IntakeField>

          <IntakeField
            label={<><Term id="employer-match">Employer match</Term> %</>}
            helper="Most NZ employers match 3% — leave as is if unsure."
          >
            <input
              type="number"
              min="0"
              max="10"
              step="0.5"
              className="input"
              value={(value.employer_rate * 100).toFixed(1)}
              onChange={(e) => onChange({ ...value, employer_rate: parseFloat(e.target.value) / 100 })}
            />
          </IntakeField>

          <IntakeField
            label={<><Term id="pir">PIR</Term> (tax rate on PIE income)</>}
            helper="If unsure, leave 28% — IRD will refund any overpayment."
          >
            <select
              className="input"
              value={value.pir}
              onChange={(e) => onChange({ ...value, pir: parseFloat(e.target.value) })}
            >
              {PIR_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </IntakeField>
        </div>
      )}
    </div>
  );
}
