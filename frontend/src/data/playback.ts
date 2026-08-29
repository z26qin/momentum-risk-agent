import type { CaseData, LoopEvent, ObservationRecord } from "./types";

export type NotePhase = "pending" | "partial" | "complete";

export function loopEvents(data: CaseData): LoopEvent[] {
  if (data.trace.loop && data.trace.loop.length > 0) {
    return data.trace.loop;
  }
  return deriveLoop(data);
}

function deriveLoop(data: CaseData): LoopEvent[] {
  const quiet = data.trace.quiet;
  const events: LoopEvent[] = [
    {
      id: "route",
      kind: "route",
      actor: "orchestrator",
      label: "ORCHESTRATOR",
      detail: quiet
        ? "routing flags: none active"
        : `spawn ${data.trace.spawned.join(", ")} on shared deadline`,
      spawned: data.trace.spawned,
      quiet,
      reason: quiet ? "NO_INVESTIGATION_NEEDED" : "deterministic_flags",
    },
  ];
  for (const spec of data.trace.specialists) {
    spec.decisions.forEach((decision, index) => {
      const step = index + 1;
      events.push({
        id: `${spec.name}-plan-${step}`,
        kind: "plan",
        actor: spec.name,
        label: spec.label,
        detail: `${decision.action ?? "call_tools"}: ${decision.hypothesis}`,
        action: decision.action,
        hypothesis: decision.hypothesis,
        reason: decision.reason,
        step,
        tool_calls: decision.tool_calls,
      });
      if ((decision.action ?? "call_tools") === "call_tools") {
        events.push({
          id: `${spec.name}-observe-${step}`,
          kind: "observe",
          actor: spec.name,
          label: spec.label,
          detail: `${(decision.observations ?? []).length} tool result(s)`,
          step,
          observations: decision.observations ?? [],
        });
      }
    });
    events.push({
      id: `${spec.name}-stop`,
      kind: "stop",
      actor: spec.name,
      label: spec.label,
      detail: `STOP: ${spec.stop_reason}`,
      reason: spec.stop_reason,
    });
  }
  events.push({
    id: "combine",
    kind: "combine",
    actor: "orchestrator",
    label: "ORCHESTRATOR",
    detail: `COMBINED STOP: ${data.trace.combined_stop}`,
    reason: data.trace.combined_stop,
  });
  return events;
}

export function notePhaseFor(events: LoopEvent[], revealed: number): NotePhase {
  const visible = events.slice(0, revealed);
  if (visible.some((event) => event.kind === "combine")) return "complete";
  if (visible.some((event) => event.kind === "route")) return "partial";
  return "pending";
}

export function snapshotObserved(lines: string[]): string[] {
  return lines.filter(
    (line) =>
      line.includes("deterministic signals") ||
      line.startsWith("mechanical unwind") ||
      line.startsWith("theme cluster") ||
      line.startsWith("structural flags"),
  );
}

export function revealedObservations(
  events: LoopEvent[],
  revealed: number,
): ObservationRecord[] {
  return events
    .slice(0, revealed)
    .filter((event) => event.kind === "observe")
    .flatMap((event) => event.observations ?? []);
}
