export default function IntakeField({ label, helper, children, htmlFor }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="label">{label}</label>
      {children}
      {helper && <div className="text-xs text-slate-500 mt-1">{helper}</div>}
    </div>
  );
}
