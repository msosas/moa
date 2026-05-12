const DEBT_KINDS = [
  ['credit_card', 'Credit card'],
  ['personal_loan', 'Personal loan'],
  ['student_loan', 'Student loan'],
  ['car_loan', 'Car loan'],
  ['bnpl', 'Buy-now-pay-later'],
  ['other', 'Other'],
];

export default function DebtRow({ row, onChange, onRemove }) {
  function patch(field, value) {
    onChange({ ...row, [field]: value });
  }

  return (
    <div className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-end">
      <div>
        <label className="label">Type</label>
        <select
          value={row.kind}
          onChange={(e) => patch('kind', e.target.value)}
          className="input"
        >
          {DEBT_KINDS.map(([id, label]) => (
            <option key={id} value={id}>{label}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="label">Balance (NZD)</label>
        <input
          type="number"
          min="0"
          className="input"
          value={row.balance}
          onChange={(e) => patch('balance', e.target.value)}
        />
      </div>
      <div>
        <label className="label">Rate (% APR)</label>
        <input
          type="number"
          min="0"
          step="0.01"
          className="input"
          value={row.rate_pct}
          onChange={(e) => patch('rate_pct', e.target.value)}
        />
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="btn-ghost text-xs"
        aria-label="Remove debt"
      >
        Remove
      </button>
    </div>
  );
}
