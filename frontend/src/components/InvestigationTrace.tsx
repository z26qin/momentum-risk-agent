import type { InvestigationTrace, LoopEvent } from "../data/types";

const KIND_LABEL: Record<LoopEvent["kind"], string> = {
  route: "ROUTE",
  plan: "PLAN",
  observe: "EXEC",
  stop: "STOP",
  combine: "NOTE",
};

function ControlButton({
  children,
  onClick,
  disabled = false,
  active = false,
}: {
  children: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`trace-control ${active ? "trace-control-active" : ""}`}
    >
      {children}
    </button>
  );
}

function eventDetail(event: LoopEvent): string {
  if (event.kind === "route") {
    return event.specialists.length
      ? `spawn ${event.specialists.join(", ")}`
      : "no specialist spawned";
  }
  if (event.kind === "plan") {
    return `${event.action ?? "plan"} · ${event.hypothesis ?? event.reason ?? ""}`;
  }
  if (event.kind === "observe") {
    return `${event.tool_name ?? "tool"} · ${(event.status ?? "unknown").toUpperCase()}`;
  }
  return event.stop_reason ?? event.reason ?? "";
}

function EventCard({ event, current }: { event: LoopEvent; current: boolean }) {
  return (
    <div className={`event-card ${current ? "event-card-current" : ""}`}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="event-kind">{KIND_LABEL[event.kind]}</span>
        <span className="font-mono text-[10px] text-muted">
          {event.specialist ?? "orchestrator"}
        </span>
        {event.planner_fallback && (
          <span className="status-chip text-amber border-amber">fallback</span>
        )}
      </div>
      <p className="font-mono text-[11px] text-ink m-0 leading-relaxed">
        {eventDetail(event)}
      </p>
      {event.kind === "observe" && (
        <div className="event-audit">
          <span>attempts {event.attempts ?? 1}</span>
          <span>post-cutoff discarded {event.discarded_post_cutoff}</span>
          {event.error_type && <span>{event.error_type}</span>}
          {event.error_message && <span>{event.error_message}</span>}
        </div>
      )}
      {event.planner_kind && (
        <span className="microcopy">planner · {event.planner_kind}</span>
      )}
    </div>
  );
}

export function InvestigationTracePanel({
  data,
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
  data: InvestigationTrace;
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
  const visible = data.loop.slice(0, revealed);
  const current = visible.at(-1);
  const routed = visible.some((event) => event.kind === "route");
  const combined = visible.some((event) => event.kind === "combine");

  return (
    <section className="trace-panel" aria-labelledby="trace-title">
      <div className="panel-title-row">
        <h2 id="trace-title" className="panel-title">Investigation trace</h2>
        <span className="microcopy">planner → executor → observe</span>
      </div>

      <div className="trace-controls">
        <ControlButton onClick={playing ? onPause : onPlay} active={playing}>
          {playing ? "PAUSE" : "PLAY LOOP"}
        </ControlButton>
        <ControlButton onClick={onStep} disabled={revealed >= data.loop.length}>STEP</ControlButton>
        <ControlButton onClick={onReset}>RESET</ControlButton>
        <ControlButton onClick={onRerun} disabled={rerunning} active={rerunning}>
          {rerunning ? "RUNNING…" : "RE-RUN AGENT"}
        </ControlButton>
        <span className="microcopy ml-1">{revealed} / {data.loop.length} events</span>
      </div>

      <div className="event-index" aria-label="Investigation event index">
        {data.loop.map((event, index) => (
          <button
            key={event.sequence}
            type="button"
            onClick={() => onJump(index + 1)}
            className={`event-index-item ${index < revealed ? "event-index-seen" : ""} ${index === revealed - 1 ? "event-index-current" : ""}`}
            aria-label={`Show ${event.kind} event ${event.sequence}`}
          >
            {event.sequence}
          </button>
        ))}
      </div>

      <div className="orchestrator-row">
        <span className="orchestrator-node" />
        <span className="font-mono text-xs">ORCHESTRATOR</span>
        <span className="microcopy">
          {!routed
            ? "waiting for immutable RiskState"
            : data.quiet
              ? "routing flags: none active"
              : `routed ${data.routed_specialists.join(", ")} · ${data.schedule}`}
        </span>
      </div>

      <div className="event-stream">
        {visible.length === 0 && <p className="empty-copy m-0">Loop playback has not started.</p>}
        {visible.map((event) => (
          <EventCard key={event.sequence} event={event} current={event === current} />
        ))}
      </div>

      <div className="specialist-grid">
        {data.specialists.map((specialist) => (
          <div key={specialist.name} className="specialist-card">
            <div className="section-heading-row">
              <span className="mono-value">{specialist.name.toUpperCase()}</span>
              <span className="microcopy">{specialist.steps} steps</span>
            </div>
            <span className="microcopy">{specialist.planner_kind}</span>
            <span className="status-chip text-amber border-amber self-start">
              {specialist.stop_reason}
            </span>
          </div>
        ))}
        {routed && data.specialists.length === 0 && (
          <div className="specialist-card"><span className="microcopy">0 specialists spawned</span></div>
        )}
      </div>

      <div className="combined-row">
        <span className="combine-node" />
        <span className="font-mono text-xs">
          {combined ? `COMBINED STOP: ${data.combined_stop}` : "COMBINED STOP: waiting"}
        </span>
        <span className="microcopy">one calibrated note · never a probability</span>
      </div>
    </section>
  );
}
