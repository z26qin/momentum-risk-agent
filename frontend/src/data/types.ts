export type MechanismStatus =
  | "triggered"
  | "watch"
  | "not_confirmed"
  | "unavailable";

export interface MechanismStates {
  bear_market_recovery_crash: MechanismStatus;
  crowded_theme_unwind: MechanismStatus;
  short_book_reversal_crash: MechanismStatus;
}

export interface BookState {
  portfolio_drawdown: number | null;
  short_loss_in_recovery: number | null;
  long_beta_126d: number | null;
  short_underlying_beta_126d: number | null;
}

export interface MechanismScores {
  book_vulnerability: number | null;
  crowded_unwind: number | null;
  dm_recovery: number | null;
  fundamental_repricing: number | null;
}

export interface SeverityState {
  score: number | null;
  label: string;
  primary_driver: string;
  mechanism_scores: MechanismScores;
  score_is_probability: false;
}

export interface RiskState {
  schema_version: "risk-state-v1";
  as_of_date: string;
  assessment_cutoff: string;
  comparison_date: string | null;
  market_regime: string;
  mechanical_unwind_state:
    | "NORMAL"
    | "FRAGILITY_BUILDING"
    | "ACTIVE_UNWIND"
    | "STABILIZING_REVERSAL";
  total_signal_count: number;
  monitoring_trigger_count: number;
  triggered_signals: string[];
  structural_flags: string[];
  mechanisms: MechanismStates;
  triggered_mechanisms: string[];
  unconfirmed_mechanisms: string[];
  book: BookState;
  theme_cluster: string[];
  severity: SeverityState;
}

export type LoopKind = "route" | "plan" | "observe" | "stop" | "combine";

export interface LoopEvent {
  sequence: number;
  kind: LoopKind;
  specialist: string | null;
  action: string | null;
  hypothesis: string | null;
  reason: string | null;
  planner_kind: string | null;
  planner_fallback: boolean;
  tool_call_id: string | null;
  tool_name: string | null;
  status: string | null;
  attempts: number | null;
  discarded_post_cutoff: number;
  error_type: string | null;
  error_message: string | null;
  stop_reason: string | null;
  specialists: string[];
}

export interface SpecialistTrace {
  name: string;
  planner_kind: string;
  planner_fallback: boolean;
  stop_reason: string;
  steps: number;
}

export interface InvestigationTrace {
  combined_stop: string;
  quiet: boolean;
  schedule: string;
  routed_specialists: string[];
  specialists: SpecialistTrace[];
  loop: LoopEvent[];
  errors: string[];
}

export interface PMNote {
  current_read: string;
  observed: string[];
  inferred: string[];
  contradicted: string[];
  not_confirmed: string[];
  citations: string[];
  what_changed: string;
  next_useful_check: string;
  score_is_probability: false;
}

export interface CaseData {
  schema_version: "investigation-console-v1";
  date: string;
  source: "export" | "live";
  elapsed_seconds: number;
  risk_state: RiskState;
  trace: InvestigationTrace;
  note: PMNote;
}

export interface CaseBundle {
  schema_version: "investigation-console-bundle-v1";
  cases: CaseData[];
}
