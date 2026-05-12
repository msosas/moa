import { useEffect } from 'react';
import { allTerms } from '../data/glossary.js';

export default function GlossaryModal({ open, onClose }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="card max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">Glossary</h2>
            <p className="text-sm text-slate-400">No jargon — every term explained in plain English.</p>
          </div>
          <button className="btn-ghost" onClick={onClose}>Close</button>
        </div>
        <ul className="space-y-4">
          {allTerms.map((t) => (
            <li key={t.id}>
              <div className="text-accent font-semibold">{t.title}</div>
              <div className="text-slate-300 text-sm">{t.plain}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
