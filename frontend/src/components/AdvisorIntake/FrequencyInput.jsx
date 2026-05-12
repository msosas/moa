const FREQ_LABELS = {
  weekly: '/ week',
  fortnightly: '/ fortnight',
  monthly: '/ month',
  annual: '/ year',
};

export default function FrequencyInput({ value, frequency, onChange, frequencies = ['weekly', 'fortnightly', 'monthly', 'annual'] }) {
  return (
    <div className="flex gap-2">
      <input
        type="number"
        min="0"
        className="input flex-1"
        value={value}
        onChange={(e) => onChange({ value: e.target.value, frequency })}
      />
      <select
        value={frequency}
        onChange={(e) => onChange({ value, frequency: e.target.value })}
        className="bg-slate-900/60 border border-slate-700 rounded-lg px-2 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-accent/60"
        aria-label="Frequency"
      >
        {frequencies.map((f) => (
          <option key={f} value={f}>{FREQ_LABELS[f]}</option>
        ))}
      </select>
    </div>
  );
}
