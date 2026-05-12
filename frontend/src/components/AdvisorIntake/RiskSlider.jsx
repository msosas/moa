const LEVELS = ['low', 'medium', 'high'];
const DESCRIPTIONS = {
  low: 'Low — capital preservation first',
  medium: 'Medium — balanced',
  high: 'High — long-term growth, comfortable with dips',
};

export default function RiskSlider({ value, onChange }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-1">
        {LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            onClick={() => onChange(level)}
            className={`flex-1 px-3 py-2 rounded-lg text-sm capitalize border transition ${
              value === level
                ? 'bg-slate-800/80 border-accent/60 text-slate-100'
                : 'bg-slate-900/40 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            {level}
          </button>
        ))}
      </div>
      <div className="text-xs text-slate-500">{DESCRIPTIONS[value]}</div>
    </div>
  );
}
