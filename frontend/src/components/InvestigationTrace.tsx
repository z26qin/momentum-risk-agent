import type { InvestigationTrace as TraceData, SpecialistTrace, StopReason } from "../data/types";
import { MAX_STEPS, OVERALL_DEADLINE_SECONDS } from "../data/types";

function StopBadge({ reason }: { reason: StopReason }) {
  const isEvidence = reason === "EVIDENCE_SUFFICIENT";
  return (
    <span
      className={`inline-block font-mono text-[10px] tracking-wide px-2.5 py-1 ${
        isEvidence
          ? "text-amber border border-amber"
          : "text-muted border border-line"
      }`}
    >
      STOP: {reason}
    </span>
  );
}

function ToolChip({ name }: { name: string }) {
  return (
    <span className="font-mono text-[9px] text-muted border border-line px-1.5 py-px bg-bg">
      {name}
    </span>
  );
}

function SpecialistCard({ spec }: { spec: SpecialistTrace }) {
  const ghostCount = MAX_STEPS - spec.decisions.length;
  const ghosts = Array.from({ length: Math.max(0, ghostCount) }, (_, i) => i);

  return (
    <div className="border border-line bg-panel flex flex-col">
      {/* Header */}
      <div className="px-3.5 py-3 border-b border-line flex justify-between items-baseline gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <span className="font-mono text-xs text-ink">{spec.label.toUpperCase()}</span>
          <span className="font-grot text-[10px] text-muted">{spec.question}</span>
        </div>
        <span className="font-mono text-[9px] text-muted whitespace-nowrap">
          {spec.planner_kind ? `${spec.planner_kind} · ` : ""}
          MAX_STEPS = {MAX_STEPS}
        </span>
      </div>

      {/* Steps */}
      <div className="px-3.5 py-2.5 flex flex-col gap-2 flex-1">
        {spec.decisions.map((d, i) => (
          <div key={i} className="flex gap-2.5 items-start">
            <span className="font-mono text-[10px] text-muted pt-0.5 w-[18px] shrink-0">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="flex flex-col gap-1 min-w-0">
              <span className="font-mono text-[11px] text-ink leading-snug">
                {d.hypothesis}
              </span>
              <div className="flex gap-1 flex-wrap">
                {d.tool_calls.map((tc) => (
                  <ToolChip key={tc.name} name={tc.name} />
                ))}
              </div>
            </div>
          </div>
        ))}

        {/* Ghost slots — the bound is visible */}
        {ghosts.map((_, i) => {
          const stepNum = spec.decisions.length + i + 1;
          return (
            <div key={`ghost-${stepNum}`} className="flex gap-2.5 items-center">
              <span className="font-mono text-[10px] text-line w-[18px] shrink-0">
                {String(stepNum).padStart(2, "0")}
              </span>
              <div className="flex-1 h-[22px] border border-dashed border-line" />
            </div>
          );
        })}
      </div>

      {/* Stop */}
      <div className="px-3.5 py-2.5 border-t border-line flex flex-col gap-1.5">
        <StopBadge reason={spec.stop_reason} />
        {spec.errors.length > 0 && (
          <span className="font-mono text-[10px] text-amber">
            {spec.errors.join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}

function DeadlineBar({
  elapsed,
  total,
}: {
  elapsed: number;
  total: number;
}) {
  const pct = Math.min(100, (elapsed / total) * 100);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-baseline">
        <span className="font-grot text-[9px] tracking-[0.14em] uppercase text-muted">
          Shared wall-clock deadline
        </span>
        <span className="font-mono text-[10px] text-ink">
          {elapsed.toFixed(1)}s / OVERALL_DEADLINE_SECONDS = {total}
        </span>
      </div>
      <div className="h-1.5 border border-line bg-bg relative">
        <div
          className="absolute inset-y-0 left-0 bg-line"
          style={{ width: `${pct}%` }}
        />
        <div
          className="absolute -top-0.5 -bottom-0.5 w-px bg-amber"
          style={{ left: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function InvestigationTracePanel({ data }: { data: TraceData }) {
  const colCount = data.specialists.length || 1;

  return (
    <div className="flex-1 min-w-0 p-5 pb-7 flex flex-col gap-4 box-border">
      <div className="flex items-baseline justify-between">
        <h2 className="font-grot text-[11px] font-semibold tracking-[0.16em] uppercase text-ink m-0">
          Investigation trace
        </h2>
        <span className="font-mono text-[10px] text-muted">
          orchestrator routes in code · run {data.run_id}
        </span>
      </div>

      {/* Orchestrator node */}
      <div className="flex items-center gap-3">
        <div className="w-2.5 h-2.5 bg-ink shrink-0" />
        <span className="font-mono text-xs text-ink">ORCHESTRATOR</span>
        <span className="font-mono text-[11px] text-muted">
          {data.quiet
            ? "routing flags: none active"
            : `spawned: ${data.spawned.join(", ")}`}
          {data.schedule ? ` · ${data.schedule}` : ""}
        </span>
      </div>

      {/* Quiet empty state */}
      {data.quiet && (
        <div className="border-l border-line ml-[5px] pl-7 flex-1 flex flex-col justify-center">
          <div className="border border-line p-12 flex flex-col items-center gap-3.5 text-center">
            <span className="font-mono text-6xl text-ink leading-none">0</span>
            <span className="font-grot text-xs tracking-[0.22em] uppercase text-ink">
              Specialists spawned
            </span>
            <span className="font-mono text-[11px] text-amber border border-amber px-3 py-1 mt-1.5">
              STOP: NO_INVESTIGATION_NEEDED
            </span>
            <p className="font-serif text-[15px] text-muted max-w-[380px] leading-relaxed mt-2">
              Quiet books spawn nobody. Routing uses flags, not leftover
              primary_driver labels — the system declining to investigate is
              the feature working.
            </p>
          </div>
        </div>
      )}

      {/* Active trace */}
      {!data.quiet && (
        <div className="border-l border-line ml-[5px] pl-7 flex flex-col gap-4 flex-1">
          {data.errors.length > 0 && (
            <div className="font-mono text-[10px] text-amber">
              {data.errors.join(" · ")}
            </div>
          )}

          <DeadlineBar
            elapsed={data.elapsed_seconds}
            total={data.deadline_seconds || OVERALL_DEADLINE_SECONDS}
          />

          {/* Specialist cards */}
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: `repeat(${colCount}, minmax(0, 1fr))`,
            }}
          >
            {data.specialists.map((sp) => (
              <SpecialistCard key={sp.name} spec={sp} />
            ))}
          </div>

          {/* Combined stop */}
          <div className="flex items-center gap-3 mt-0.5">
            <div className="w-2.5 h-2.5 bg-amber shrink-0 -ml-[36px]" />
            <span className="font-mono text-xs text-ink">
              COMBINED STOP: {data.combined_stop}
            </span>
            <span className="font-mono text-[10px] text-muted">
              one calibrated note · never a crash score
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
