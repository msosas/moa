import { useRef, useState } from 'react';
import { useAdvisorPlan } from '../hooks/useAdvisorPlan.js';
import { useNarrativeConfig } from '../hooks/useNarrativeConfig.js';
import AdvisorIntake from './AdvisorIntake/index.jsx';
import AdvisorPlan from './AdvisorPlan/index.jsx';
import GlossaryModal from './GlossaryModal.jsx';
import MarketContext from './MarketContext.jsx';
import NarrativeSettings from './NarrativeSettings.jsx';

export default function AdvisorPage() {
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [lastProfile, setLastProfile] = useState(null);
  const { data, loading, error, submit } = useAdvisorPlan();
  const { config: narrativeConfig, setProvider, setModel } = useNarrativeConfig();
  const planRef = useRef(null);

  async function handleSubmit(profile) {
    setLastProfile(profile);
    await submit(profile, narrativeConfig);
    // Scroll to results after the render commits.
    setTimeout(() => {
      planRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  return (
    <div className="min-h-full">
      <header className="border-b border-slate-800/60 bg-slate-950/40 backdrop-blur sticky top-0 z-20 print:hidden">
        <div className="max-w-3xl mx-auto px-6 py-3 flex items-center justify-between">
          <div>
            <div className="text-xl font-bold tracking-tight">FinPath <span className="text-accent">AI</span></div>
            <div className="text-xs text-slate-400">A holistic look at your money — one plan, one professional answer.</div>
          </div>
          <button className="btn-ghost text-sm" onClick={() => setGlossaryOpen(true)}>Glossary</button>
        </div>
      </header>

      <div className="print:hidden">
        <MarketContext />
      </div>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        <section className="print:hidden">
          <h2 className="text-lg font-semibold mb-3">Tell me about your money</h2>
          <p className="text-sm text-slate-400 mb-4">
            The more honest the inputs, the more useful the answer. Nothing is stored.
          </p>
          <div className="mb-4">
            <NarrativeSettings
              config={narrativeConfig}
              onProviderChange={setProvider}
              onModelChange={setModel}
            />
          </div>
          <AdvisorIntake onSubmit={handleSubmit} loading={loading} error={error} />
        </section>

        <section ref={planRef}>
          {data && lastProfile && (
            <AdvisorPlan response={data} profile={lastProfile} narrativeConfig={narrativeConfig} />
          )}
        </section>
      </main>

      <footer className="text-center text-xs text-slate-500 py-6">
        Educational POC — not personalised financial advice. Always consult a registered adviser before acting.
      </footer>

      <GlossaryModal open={glossaryOpen} onClose={() => setGlossaryOpen(false)} />
    </div>
  );
}
