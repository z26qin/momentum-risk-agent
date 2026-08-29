import { useEffect, useState } from "react";
import { ALL_CASES, loadCases } from "./data/cases";
import type { CaseData } from "./data/types";
import { RiskStatePanel } from "./components/RiskStatePanel";
import { InvestigationTracePanel } from "./components/InvestigationTrace";
import { PMNotePanel } from "./components/PMNote";

function CaseTab({
  c,
  active,
  onClick,
}: {
  c: CaseData;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left px-3.5 py-2 border transition-colors duration-100 ${
        active
          ? "border-amber bg-panel text-ink"
          : "border-line text-muted hover:border-muted"
      }`}
    >
      <span className="block font-mono text-xs">{c.date}</span>
      <span className="block font-grot text-[9px] tracking-[0.12em] uppercase mt-0.5">
        {c.label}
      </span>
    </button>
  );
}

export default function App() {
  const [cases, setCases] = useState<CaseData[]>(ALL_CASES);
  const [caseId, setCaseId] = useState(ALL_CASES[0].id);

  useEffect(() => {
    let cancelled = false;
    loadCases().then((next) => {
      if (cancelled || next.length === 0) return;
      setCases(next);
      setCaseId((id) => (next.some((item) => item.id === id) ? id : next[0].id));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const current = cases.find((c) => c.id === caseId) ?? cases[0] ?? ALL_CASES[0];

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      {/* ─── Header ─── */}
      <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 px-5 lg:px-7 py-4 border-b border-line">
        <div className="flex flex-col gap-0.5">
          <h1 className="font-mono text-sm font-medium tracking-wide text-ink m-0">
            MOMENTUM-RISK-AGENT
          </h1>
          <span className="font-grot text-[10px] tracking-[0.18em] uppercase text-muted">
            Investigation console
          </span>
        </div>

        <div className="flex gap-2">
          {cases.map((c) => (
            <CaseTab
              key={c.id}
              c={c}
              active={c.id === caseId}
              onClick={() => setCaseId(c.id)}
            />
          ))}
        </div>

        <div className="flex flex-col items-end gap-0.5">
          <span className="font-mono text-[11px] text-muted">
            evidence cutoff {current.cutoff}
          </span>
          <span className="font-mono text-[11px] text-muted">
            horizon {current.horizon_days}d · frozen case, not a live call
          </span>
        </div>
      </header>

      {/* ─── Three-column console ─── */}
      <div className="flex flex-col lg:flex-row flex-1 items-stretch">
        <RiskStatePanel data={current.risk_state} />
        <InvestigationTracePanel data={current.trace} />
        <PMNotePanel data={current.note} />
      </div>

      {/* ─── Invariant footer ─── */}
      <footer className="flex flex-col sm:flex-row justify-between items-start sm:items-center px-5 lg:px-7 py-2.5 border-t border-line gap-2">
        <span className="font-mono text-[10px] text-muted">
          score_is_probability = {String(current.risk_state.score_is_probability)} · evidence after cutoff rejected ·
          missing evidence stays missing · trade language stripped
        </span>
        <span className="font-mono text-[10px] text-muted">
          invariants enforced in Python, not prompts
        </span>
      </footer>
    </div>
  );
}
