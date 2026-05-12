import { useState } from 'react';

export default function IntakeSection({ title, summary, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-slate-900/30 transition"
      >
        <div>
          <div className="font-semibold text-slate-100">{title}</div>
          {summary && !open && <div className="text-xs text-slate-500 mt-0.5">{summary}</div>}
        </div>
        <span className={`text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`}>▸</span>
      </button>
      {open && <div className="px-5 pb-5 pt-1 space-y-4 border-t border-slate-800/60">{children}</div>}
    </section>
  );
}
