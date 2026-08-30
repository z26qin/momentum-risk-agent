import { useEffect, useState } from "react";
import { PMNotePanel } from "./components/PMNote";
import { RiskStatePanel } from "./components/RiskStatePanel";
import { loadCases } from "./data/cases";
import type { CaseData } from "./data/types";

export default function App() {
  const [cases, setCases] = useState<CaseData[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadCases()
      .then((loaded) => {
        if (!active) return;
        setCases(loaded);
        setSelectedDate(loaded[0]?.date ?? "");
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => { active = false; };
  }, []);

  const current = cases.find((item) => item.date === selectedDate);

  if (error) return <main className="load-state">Console unavailable: {error}</main>;
  if (!current) return <main className="load-state">Loading frozen investigations…</main>;

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      <header className="app-header">
        <div>
          <h1 className="font-mono text-sm tracking-wide m-0">MOMENTUM-RISK-AGENT</h1>
          <span className="app-kicker">Investigation console</span>
        </div>
        <nav className="case-tabs" aria-label="Frozen investigation date">
          {cases.map((item) => (
            <button
              key={item.date}
              type="button"
              className={`case-tab ${item.date === current.date ? "case-tab-active" : ""}`}
              onClick={() => setSelectedDate(item.date)}
            >
              {item.date}
            </button>
          ))}
        </nav>
        <div className="header-meta">
          <span>cutoff {current.risk_state.assessment_cutoff}</span>
          <span>{current.source} · heuristic contract</span>
        </div>
      </header>

      <main className="console-grid">
        <RiskStatePanel data={current.risk_state} />
        <section className="trace-placeholder" aria-labelledby="trace-title">
          <div className="panel-title-row">
            <h2 id="trace-title" className="panel-title">Investigation trace</h2>
            <span className="microcopy">{current.trace.schedule}</span>
          </div>
          <div className="trace-summary">
            <span className="trace-orbit">{current.trace.loop.length}</span>
            <p className="font-serif text-xl m-0">Bounded agent loop</p>
            <p className="microcopy m-0 text-center">
              {current.trace.routed_specialists.length
                ? `routed to ${current.trace.routed_specialists.join(", ")}`
                : "no specialist routed"}
            </p>
            <span className="status-chip text-amber border-amber">{current.trace.combined_stop}</span>
          </div>
        </section>
        <PMNotePanel data={current.note} />
      </main>

      <footer className="app-footer">
        <span>score_is_probability = false · post-cutoff evidence rejected</span>
        <span>risk invariants enforced in Python</span>
      </footer>
    </div>
  );
}
