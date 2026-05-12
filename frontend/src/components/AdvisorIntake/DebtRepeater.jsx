import DebtRow from './DebtRow.jsx';

function newRow() {
  return {
    id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : String(Math.random()),
    kind: 'credit_card',
    balance: 0,
    rate_pct: 19.95,
  };
}

export default function DebtRepeater({ rows, onChange }) {
  function add() {
    onChange([...rows, newRow()]);
  }
  function update(id, patch) {
    onChange(rows.map((r) => (r.id === id ? patch : r)));
  }
  function remove(id) {
    onChange(rows.filter((r) => r.id !== id));
  }

  return (
    <div className="space-y-3">
      {rows.length === 0 && (
        <div className="text-xs text-slate-500">No other debts — that's the goal.</div>
      )}
      {rows.map((row) => (
        <DebtRow
          key={row.id}
          row={row}
          onChange={(next) => update(row.id, next)}
          onRemove={() => remove(row.id)}
        />
      ))}
      <button type="button" onClick={add} className="btn-ghost text-sm">
        + Add a debt
      </button>
    </div>
  );
}
