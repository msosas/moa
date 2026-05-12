import Term from './Term.jsx';
import { useMarketRates } from '../hooks/useMarketRates.js';

const fmtPct = (v) => `${(v * 100).toFixed(2)}%`;

export default function MarketContext() {
  const { data, loading, error } = useMarketRates();

  if (loading) return <Bar><span className="text-slate-500">Loading rates…</span></Bar>;
  if (error) return <Bar><span className="text-risk text-sm">{error.message}</span></Bar>;
  if (!data) return null;

  return (
    <Bar>
      <Tile label={<Term id="ocr">OCR</Term>} value={fmtPct(data.central_bank_rate)} />
      <Tile label="3y fixed mortgage" value={fmtPct(data.mortgage.fixed_3y)} />
      <Tile label="12-mo term deposit" value={fmtPct(data.savings.term_deposit_12m)} />
      {data.source !== 'mock' && (
        <span className="text-xs text-slate-500">
          {data.source === 'live' ? 'Live rates' : 'Live data offline — using mock'}
        </span>
      )}
    </Bar>
  );
}

function Bar({ children }) {
  return (
    <div className="sticky top-[57px] z-10 backdrop-blur bg-slate-950/60 border-b border-slate-800/60">
      <div className="max-w-3xl mx-auto px-6 py-2 flex items-center gap-6 text-xs">{children}</div>
    </div>
  );
}

function Tile({ label, value }) {
  return (
    <span className="flex items-center gap-2">
      <span className="text-slate-500">{label}</span>
      <span className="tabular-nums text-slate-200">{value}</span>
    </span>
  );
}
