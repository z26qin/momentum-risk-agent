/**
 * Frontend types mirroring the Python agent data model.
 *
 * These map 1:1 to the JSON that `run_orchestrated_investigation()` emits.
 * The frontend never computes risk — it reads pre-classified buckets.
 *
 * Data flow:
 *   run_orchestrated_investigation()
 *     → scripts/export_frontend_cases.py  (frozen replay)
 *     → POST /api/run/:id                 (live re-run)
 *       → CaseData
 *         → RiskState (immutable input) | loop playback | PM note
 */

// ── RiskState (immutable, code-owned) ──────────────────────────────

export type TriggerStatus = "available" | "unavailable";

export interface ScorecardSignal {
  metric: string;
  current_value: number | null;
  threshold: number | string;
  triggered: boolean | null;
  status: TriggerStatus;
}

export type MechanismStatus = "triggered" | "watch" | "not_confirmed";

export interface ThemeProxy {
  cluster_symbols: string[];
  cluster_average_residual_correlation: number;
  cluster_residual_loss_5d: number;
  cluster_exposure_share: number;
  trigger: boolean;
}

export type UnwindState =
  | "NORMAL"
  | "FRAGILITY_BUILDING"
  | "RECOVERY_CRASH_SETUP"
  | "ACTIVE_UNWIND";

export interface RiskState {
  scorecard: ScorecardSignal[];
  trigger_count: string; // always "n / 4" — same four PM book-stress channels as the agent note
  mechanisms: Record<string, MechanismStatus>;
  theme_proxy: ThemeProxy | null;
  unwind_state: UnwindState;
  primary_driver?: string | null;
  score_is_probability: false;
}

// ── Investigation trace (orchestrator + specialist loops) ──────────

export type StopReason =
  | "EVIDENCE_SUFFICIENT"
  | "EVIDENCE_CONTRADICTED"
  | "NO_INVESTIGATION_NEEDED"
  | "UNRESOLVABLE"
  | "MAX_STEPS"
  | "DEADLINE_EXCEEDED"
  | "ESCALATED"
  | "MALFORMED_PLANNER_OUTPUT"
  | "PLANNER_TIMEOUT";

export interface ToolCallRecord {
  name: string;
  args: Record<string, unknown>;
}

export interface ObservationRecord {
  name: string;
  status: string;
  args: Record<string, unknown>;
  summary: string;
  elapsed_ms: number;
  discarded_post_cutoff: number;
}

export interface DecisionRecord {
  action?: "call_tools" | "finish" | "escalate";
  hypothesis: string;
  reason?: string;
  tool_calls: ToolCallRecord[];
  observations?: ObservationRecord[];
}

export type LoopKind = "route" | "plan" | "observe" | "stop" | "combine";

export interface LoopEvent {
  id: string;
  kind: LoopKind;
  actor: string;
  label: string;
  detail: string;
  reason?: string;
  action?: string;
  hypothesis?: string;
  step?: number;
  quiet?: boolean;
  spawned?: string[];
  tool_calls?: ToolCallRecord[];
  observations?: ObservationRecord[];
}

export interface SpecialistTrace {
  name: string;
  label: string;
  question: string;
  focus: string;
  allowed_tools: string[];
  planner_kind: string;
  decisions: DecisionRecord[];
  stop_reason: StopReason;
  errors: string[];
  elapsed_seconds: number;
}

export interface InvestigationTrace {
  run_id: string;
  quiet: boolean;
  spawned: string[];
  schedule: string;
  deadline_seconds: number;
  elapsed_seconds: number;
  errors: string[];
  specialists: SpecialistTrace[];
  loop?: LoopEvent[];
  combined_stop: StopReason;
}

// ── PM note (calibrated buckets — classified in Python code) ───────

export interface PMNote {
  current_read: string;
  observed: string[];
  inferred: string[];
  against: string[];      // Python calls this "contradicted"
  not_confirmed: string[];
  citations: string[];
  what_changed: string;
  next_useful_check: string;
  score_is_probability: false; // always false — invariant #2
}

// ── Top-level case ─────────────────────────────────────────────────

export interface CaseData {
  id: string;
  label: string;
  date: string;
  cutoff: string;
  horizon_days: number;
  source?: "export" | "live";
  risk_state: RiskState;
  trace: InvestigationTrace;
  note: PMNote;
}

export const MAX_STEPS = 6;
export const OVERALL_DEADLINE_SECONDS = 10;
