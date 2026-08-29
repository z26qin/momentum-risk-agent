import { useEffect, useMemo, useState } from "react";
import { ALL_CASES, loadCases, rerunCase } from "./data/cases";
import {
  loopEvents,
  notePhaseFor,
  revealedObservations,
  snapshotObserved,
} from "./data/playback";
import type { CaseData } from "./data/types";
import { useLoopPlayback } from "./hooks/useLoopPlayback";
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
  const [rerunning, setRerunning] = useState(false);
  const [rerunError, setRerunError] = useState<string | null>(null);

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
  const events = useMemo(() => loopEvents(current), [current]);
  const playback = useLoopPlayback(current.trace.run_id, events.length);
  const phase = notePhaseFor(events, playback.revealed);
  const liveObserved = [
    ...(phase === "pending" ? [] : snapshotObserved(current.note.observed)),
    ...revealedObservations(events, playback.revealed).map((item) => item.summary),
  ];

  async function handleRerun() {
    setRerunning(true);
    setRerunError(null);
    try {
      const next = await rerunCase(current.id);
      setCases((prev) => prev.map((item) => (item.id === next.id ? next : item)));
    } catch (error) {
      setRerunError(error instanceof Error ? error.message : String(error));
    } finally {
      setRerunning(false);
    }
  }

  const live = current.source === "live";

  return (
    <div className="min-h-screen flex flex-col bg-bg">
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
            horizon {current.horizon_days}d · RiskState frozen ·{" "}
            {live ? `live run ${current.trace.run_id}` : "replay exported loop"}
          </span>
          {rerunError && (
            <span className="font-mono text-[10px] text-amber max-w-[280px] text-right">
              {rerunError}
            </span>
          )}
        </div>
      </header>

      <div className="flex flex-col lg:flex-row flex-1 items-stretch">
        <RiskStatePanel data={current.risk_state} />
        <InvestigationTracePanel
          data={current.trace}
          events={events}
          revealed={playback.revealed}
          playing={playback.playing}
          onPlay={playback.play}
          onPause={playback.pause}
          onStep={playback.step}
          onReset={playback.reset}
          onJump={playback.jump}
          onRerun={handleRerun}
          rerunning={rerunning}
        />
        <PMNotePanel
          data={current.note}
          phase={phase}
          liveObserved={liveObserved}
        />
      </div>

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
