import type { LoopEvent } from "./types";

export type NotePhase = "pending" | "partial" | "complete";

export function notePhaseFor(events: LoopEvent[], revealed: number): NotePhase {
  const visible = events.slice(0, revealed);
  if (visible.some((event) => event.kind === "combine")) return "complete";
  if (visible.some((event) => event.kind === "route")) return "partial";
  return "pending";
}
