import type {
  InvestigationTrace as TraceData,
  LoopEvent,
  ObservationRecord,
  SpecialistTrace,
  StopReason,
} from "../data/types";
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

function KindChip({ kind }: { kind: LoopEvent["kind"] }) {
  const labels: Record<LoopEvent["kind"], string> = {
    route: "ROUTE",
    plan: "PLAN",
    observe: "EXEC",
    stop: "STOP",
    combine: "NOTE",
  };
  return (
    <span className="font-mono text-[9px] tracking-wide text-amber border border-amber px-1.5 py-px">
      {labels[kind]}
    </span>
  );
}

function ObservationLine({ item }: { item: ObservationRecord }) {
  const ok = item.status === "ok";
  return (
    <div className="flex gap-2 items-start">
      <span
        className={`font-mono text-[9px] tracking-wide shrink-0 mt-0.5 ${
          ok ? "text-amber" : "text-muted"
        }`}
      >
        {item.status.toUpperCase()}
      </span>
      <span className="font-mono text-[10px] text-muted leading-relaxed">
        {item.summary}
      </span>
    </div>
  );
}

function SpecialistCard({
  spec,
  revealedDecisions,
  showStop,
}: {
  spec: SpecialistTrace;
  revealedDecisions: number;
  showStop: boolean;
}) {
  const visible = spec.decisions.slice(0, revealedDecisions);
  const ghostCount = MAX_STEPS - visible.length;
  const ghosts = Array.from({ length: Math.max(0, ghostCount) }, (_, i) => i);

  return (
    <div className="border border-line bg-panel flex flex-col">
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

      <div className="px-3.5 py-2.5 flex flex-col gap-2 flex-1">
        {visible.map((d, i) => (
          <div key={i} className="flex gap-2.5 items-start">
            <span className="font-mono text-[10px] text-muted pt-0.5 w-[18px] shrink-0">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="flex flex-col gap-1 min-w-0">
              <div className="flex gap-1.5 items-baseline flex-wrap">
                <span className="font-mono text-[9px] text-amber">
                  {(d.action ?? "call_tools").toUpperCase()}
                </span>
                <span className="font-mono text-[11px] text-ink leading-snug">
                  {d.hypothesis}
                </span>
              </div>
              {d.reason && (
                <span className="font-mono text-[10px] text-muted">{d.reason}</span>
              )}
              {d.tool_calls.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {d.tool_calls.map((tc) => (
                    <ToolChip key={`${tc.name}-${JSON.stringify(tc.args)}`} name={tc.name} />
                  ))}
                </div>
              )}
              {(d.observations ?? []).length > 0 && (
                <div className="flex flex-col gap-1 pt-1 border-l border-line pl-2">
                  {(d.observations ?? []).map((obs, oi) => (
                    <ObservationLine key={`${obs.name}-${oi}`} item={obs} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {ghosts.map((_, i) => {
          const stepNum = visible.length + i + 1;
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

      <div className="px-3.5 py-2.5 border-t border-line flex flex-col gap-1.5 min-h-[42px]">
        {showStop ? (
          <>
            <StopBadge reason={spec.stop_reason} />
            {spec.errors.length > 0 && (
              <span className="font-mono text-[10px] text-amber">
                {spec.errors.join(" · ")}
              </span>
            )}
          </>
        ) : (
          <span className="font-mono text-[10px] text-muted">loop running</span>
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

function ControlButton({
  label,
  onClick,
  disabled,
  active,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`font-mono text-[10px] tracking-wide px-2 py-1 border ${
        active
          ? "border-amber text-amber"
          : "border-line text-muted hover:border-muted"
      } disabled:opacity-40 disabled:hover:border-line`}
    >
      {label}
    </button>
  );
}

export function InvestigationTracePanel({
  data,
  events,
  revealed,
  playing,
  onPlay,
  onPause,
  onStep,
  onReset,
  onJump,
  onRerun,
  rerunning,
}: {
  data: TraceData;
  events: LoopEvent[];
  revealed: number;
  playing: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStep: () => void;
  onReset: () => void;
  onJump: (count: number) => void;
  onRerun: () => void;
  rerunning: boolean;
}) {
  const visible = events.slice(0, revealed);
  const current = visible[visible.length - 1];
  const colCount = data.specialists.length || 1;
  const progress = events.length === 0 ? 0 : revealed / events.length;
  const shownElapsed = data.elapsed_seconds * progress;
  const specialistReveal = Object.fromEntries(
    data.specialists.map((spec) => {
      const plans = visible.filter(
        (event) => event.kind === "plan" && event.actor === spec.name,
      ).length;
      const stopped = visible.some(
        (event) => event.kind === "stop" && event.actor === spec.name,
      );
      return [spec.name, { plans, stopped }];
    }),
  );
  const routed = visible.some((event) => event.kind === "route");
  const combined = visible.some((event) => event.kind === "combine");

  return (
    <div className="flex-1 min-w-0 p-5 pb-7 flex flex-col gap-4 box-border">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-grot text-[11px] font-semibold tracking-[0.16em] uppercase text-ink m-0">
          Investigation trace
        </h2>
        <span className="font-mono text-[10px] text-muted">
          planner → executor → observe · run {data.run_id}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <ControlButton
          label={playing ? "PAUSE" : "PLAY LOOP"}
          onClick={playing ? onPause : onPlay}
          active={playing}
        />
        <ControlButton label="STEP" onClick={onStep} disabled={revealed >= events.length} />
        <ControlButton label="RESET" onClick={onReset} />
        <ControlButton
          label={rerunning ? "RUNNING…" : "RE-RUN AGENT"}
          onClick={onRerun}
          disabled={rerunning}
          active={rerunning}
        />
        <span className="font-mono text-[10px] text-muted ml-1">
          {revealed} / {events.length} loop events
          {current ? ` · ${current.kind}` : ""}
        </span>
      </div>

      <div className="flex flex-wrap gap-1">
        {events.map((event, index) => {
          const on = index < revealed;
          const here = index === revealed - 1;
          return (
            <button
              key={event.id}
              type="button"
              onClick={() => onJump(index + 1)}
              className={`font-mono text-[9px] tracking-wide px-1.5 py-1 border ${
                here
                  ? "border-amber text-amber"
                  : on
                    ? "border-line text-ink"
                    : "border-dashed border-line text-line"
              }`}
            >
              {event.kind === "observe" ? "exec" : event.kind}
              {event.step ? ` ${event.step}` : ""}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <div className="w-2.5 h-2.5 bg-ink shrink-0" />
        <span className="font-mono text-xs text-ink">ORCHESTRATOR</span>
        <span className="font-mono text-[11px] text-muted">
          {!routed
            ? "waiting for RiskState flags"
            : data.quiet
              ? "routing flags: none active"
              : `spawned: ${data.spawned.join(", ")}`}
          {data.schedule ? ` · ${data.schedule}` : ""}
        </span>
      </div>

      {data.quiet && routed && (
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

      {!data.quiet && (
        <div className="border-l border-line ml-[5px] pl-7 flex flex-col gap-4 flex-1">
          {data.errors.length > 0 && (
            <div className="font-mono text-[10px] text-amber">
              {data.errors.join(" · ")}
            </div>
          )}

          <DeadlineBar
            elapsed={shownElapsed}
            total={data.deadline_seconds || OVERALL_DEADLINE_SECONDS}
          />

          {current && current.kind !== "route" && (
            <div className="border border-line p-2.5 flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <KindChip kind={current.kind} />
                <span className="font-mono text-[11px] text-ink">{current.label}</span>
              </div>
              <span className="font-mono text-[11px] text-muted">{current.detail}</span>
              {current.kind === "observe" &&
                (current.observations ?? []).map((obs, i) => (
                  <ObservationLine key={`${obs.name}-${i}`} item={obs} />
                ))}
            </div>
          )}

          {routed && (
            <div
              className="grid gap-4"
              style={{
                gridTemplateColumns: `repeat(${colCount}, minmax(0, 1fr))`,
              }}
            >
              {data.specialists.map((sp) => (
                <SpecialistCard
                  key={sp.name}
                  spec={{
                    ...sp,
                    decisions: sp.decisions.map((decision, index) => {
                      const observeSeen = visible.some(
                        (event) =>
                          event.kind === "observe" &&
                          event.actor === sp.name &&
                          event.step === index + 1,
                      );
                      return {
                        ...decision,
                        observations: observeSeen ? decision.observations : [],
                      };
                    }),
                  }}
                  revealedDecisions={specialistReveal[sp.name]?.plans ?? 0}
                  showStop={Boolean(specialistReveal[sp.name]?.stopped)}
                />
              ))}
            </div>
          )}

          <div className="flex items-center gap-3 mt-0.5">
            <div className="w-2.5 h-2.5 bg-amber shrink-0 -ml-[36px]" />
            <span className="font-mono text-xs text-ink">
              {combined
                ? `COMBINED STOP: ${data.combined_stop}`
                : "COMBINED STOP: waiting for specialist loops"}
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
