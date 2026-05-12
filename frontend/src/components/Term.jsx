import { useState, useRef, useEffect } from 'react';
import { getTerm } from '../data/glossary.js';

export default function Term({ id, children }) {
  const entry = getTerm(id);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  if (!entry) return <span>{children}</span>;

  return (
    <span ref={ref} className="relative inline-block">
      <button
        type="button"
        className="term"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => { e.preventDefault(); setOpen((v) => !v); }}
        aria-describedby={`term-${id}`}
      >
        {children}
      </button>
      {open && (
        <span
          id={`term-${id}`}
          role="tooltip"
          className="absolute z-30 left-0 top-full mt-2 w-72 p-3 text-sm bg-slate-900 border border-slate-700 rounded-lg shadow-card text-slate-200 normal-case"
        >
          <span className="block font-semibold text-accent mb-1">{entry.title}</span>
          <span className="block text-slate-300">{entry.plain}</span>
        </span>
      )}
    </span>
  );
}
