import { useEffect, useState } from "react";
import { InvestigationTracePanel } from "./components/InvestigationTrace";
import { PMNotePanel } from "./components/PMNote";
import { RiskStatePanel } from "./components/RiskStatePanel";
import { loadCases, rerunCase } from "./data/cases";
import { notePhaseFor } from "./data/playback";
import type { CaseData } from "./data/types";
import { useLoopPlayback } from "./hooks/useLoopPlayback";

export default function App() {
  const [cases, setCases] = useState<CaseData[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [rerunError, setRerunError] = useState<string | null>(null);

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

  return <LoadedConsole
    key={`${current.date}:${current.source}:${current.elapsed_seconds}`}
    cases={cases}
    current={current}
    selectedDate={selectedDate}
    setSelectedDate={setSelectedDate}
    setCases={setCases}
    rerunning={rerunning}
    setRerunning={setRerunning}
    rerunError={rerunError}
    setRerunError={setRerunError}
  />;
}

function LoadedConsole({
  cases,
  current,
  selectedDate,
  setSelectedDate,
  setCases,
  rerunning,
  setRerunning,
  rerunError,
  setRerunError,
}: {
  cases: CaseData[];
  current: CaseData;
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  setCases: React.Dispatch<React.SetStateAction<CaseData[]>>;
  rerunning: boolean;
  setRerunning: (value: boolean) => void;
  rerunError: string | null;
  setRerunError: (value: string | null) => void;
}) {
  const playback = useLoopPlayback(current.trace.loop.length);
  const phase = notePhaseFor(current.trace.loop, playback.revealed);

  async function handleRerun() {
    setRerunning(true);
    setRerunError(null);
    try {
      const next = await rerunCase(current.date);
      setCases((previous) => previous.map((item) => item.date === next.date ? next : item));
    } catch (reason) {
      setRerunError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRerunning(false);
    }
  }

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
              className={`case-tab ${item.date === selectedDate ? "case-tab-active" : ""}`}
              onClick={() => setSelectedDate(item.date)}
            >
              {item.date}
            </button>
          ))}
        </nav>
        <div className="header-meta">
          <span>cutoff {current.risk_state.assessment_cutoff}</span>
          <span>{current.source} · heuristic contract</span>
          {rerunError && <span className="text-amber">{rerunError}</span>}
        </div>
      </header>

      <main className="console-grid">
        <RiskStatePanel data={current.risk_state} />
        <InvestigationTracePanel
          data={current.trace}
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
        <PMNotePanel data={current.note} phase={phase} />
      </main>

      <footer className="app-footer">
        <span>score_is_probability = false · post-cutoff evidence rejected</span>
        <span>risk invariants enforced in Python</span>
      </footer>
    </div>
  );
}
