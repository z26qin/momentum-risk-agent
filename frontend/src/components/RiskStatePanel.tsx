import type { RiskState, MechanismStatus } from "../data/types";

const SEVERITY_POSITIONS: Record<string, string> = {
  NORMAL: "12%",
  FRAGILITY_BUILDING: "62%",
  RECOVERY_CRASH_SETUP: "80%",
  ACTIVE_UNWIND: "95%",
};

function SignalRow({
  metric,
  current_value,
  threshold,
  triggered,
}: {
  metric: string;
  current_value: number | null;
  threshold: number | string;
  triggered: boolean | null;
}) {
  const trig = triggered === true;
  return (
    <div className="flex items-center gap-2.5 p-2.5 border border-line bg-bg">
      <span
        className={`font-mono text-[9px] tracking-wide shrink-0 px-1.5 py-0.5 ${
          trig
            ? "bg-amber text-bg"
            : "text-muted border border-line"
        }`}
      >
        {trig ? "TRIG" : "—"}
      </span>
      <div className="min-w-0 flex-1">
        <div
          className={`font-mono text-[11px] truncate ${
            trig ? "text-ink" : "text-muted"
          }`}
        >
          {metric}
        </div>
        <div className="font-mono text-[10px] text-muted">
          {current_value !== null
            ? `${current_value.toFixed(3)} vs thr ${
                typeof threshold === "number"
                  ? threshold.toFixed(3)
                  : threshold
              }`
            : String(threshold)}
        </div>
      </div>
    </div>
  );
}

function MechanismCard({
  name,
  status,
  themeProxy,
}: {
  name: string;
  status: MechanismStatus;
  themeProxy: RiskState["theme_proxy"];
}) {
  const statusStyles: Record<MechanismStatus, string> = {
    triggered:
      "bg-amber text-bg font-mono text-[9px] tracking-wide px-1.5 py-0.5 whitespace-nowrap",
    watch:
      "text-amber border border-amber font-mono text-[9px] tracking-wide px-1.5 py-0.5 whitespace-nowrap",
    not_confirmed:
      "text-muted border border-dashed border-line font-mono text-[9px] tracking-wide px-1.5 py-0.5 whitespace-nowrap",
  };
  const statusLabels: Record<MechanismStatus, string> = {
    triggered: "TRIGGERED",
    watch: "WATCH",
    not_confirmed: "NOT CONFIRMED",
  };
  const showCluster =
    name === "crowded_theme_unwind" && themeProxy?.cluster_symbols?.length;

  return (
    <div className="flex flex-col gap-1.5 p-2.5 border border-line">
      <div className="flex justify-between items-center gap-2">
        <span className="font-mono text-[11px] text-ink">{name}</span>
        <span className={statusStyles[status]}>{statusLabels[status]}</span>
      </div>
      {showCluster && themeProxy && (
        <div className="flex items-center gap-1.5 flex-wrap">
          {themeProxy.cluster_symbols.map((t) => (
            <span
              key={t}
              className="font-mono text-[10px] text-amber border border-amber px-1.5 py-px"
            >
              {t}
            </span>
          ))}
          <span className="font-mono text-[10px] text-muted">
            corr {themeProxy.cluster_average_residual_correlation.toFixed(3)} ·
            5d -{(themeProxy.cluster_residual_loss_5d * 100).toFixed(1)}% · exp{" "}
            {themeProxy.cluster_exposure_share.toFixed(2)}
          </span>
        </div>
      )}
    </div>
  );
}

export function RiskStatePanel({ data }: { data: RiskState }) {
  const sevPos = SEVERITY_POSITIONS[data.unwind_state] ?? "12%";

  return (
    <div className="w-full lg:w-[356px] shrink-0 lg:border-r border-line bg-panel p-5 pb-7 flex flex-col gap-6 box-border">
      <div className="flex items-baseline justify-between">
        <h2 className="font-grot text-[11px] font-semibold tracking-[0.16em] uppercase text-ink m-0">
          RiskState
        </h2>
        <span className="font-mono text-[10px] text-muted">
          immutable · code-owned
        </span>
      </div>

      {/* Signals */}
      <div className="flex flex-col gap-2.5">
        <div className="flex justify-between items-baseline">
          <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
            Deterministic signals
          </span>
          <span className="font-mono text-[11px] text-ink">
            {data.trigger_count} triggered
          </span>
        </div>
        <div className="flex flex-col gap-1.5">
          {data.scorecard.map((s) => (
            <SignalRow key={s.metric} {...s} />
          ))}
        </div>
      </div>

      {/* Mechanisms */}
      <div className="flex flex-col gap-2.5">
        <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
          Mechanism status
        </span>
        <div className="flex flex-col gap-1.5">
          {Object.entries(data.mechanisms).map(([name, status]) => (
            <MechanismCard
              key={name}
              name={name}
              status={status}
              themeProxy={data.theme_proxy}
            />
          ))}
        </div>
      </div>

      {/* Severity band */}
      <div className="flex flex-col gap-3 mt-auto">
        <div className="flex justify-between items-baseline">
          <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
            Relative severity band
          </span>
          <span className="font-mono text-[9px] text-muted">
            not a probability
          </span>
        </div>
        <div className="relative pt-3">
          {/* Caret */}
          <div
            className="absolute top-0"
            style={{ left: sevPos, marginLeft: -5 }}
          >
            <div
              className="w-0 h-0"
              style={{
                borderLeft: "5px solid transparent",
                borderRight: "5px solid transparent",
                borderTop: "7px solid var(--color-amber)",
              }}
            />
          </div>
          <div className="grid grid-cols-4 border border-line bg-bg">
            {["QUIET", "WATCH", "FRAGILITY", "UNWIND"].map((label, i) => (
              <div
                key={label}
                className={`py-2 text-center font-mono text-[9px] tracking-wide text-muted ${
                  i < 3 ? "border-r border-line" : ""
                }`}
              >
                {label}
              </div>
            ))}
          </div>
        </div>
        <div className="font-mono text-[11px] text-ink">
          unwind_state = {data.unwind_state}
        </div>
        {data.primary_driver && (
          <div className="font-mono text-[10px] text-muted">
            {data.unwind_state === "NORMAL"
              ? `leftover primary_driver = ${data.primary_driver} · not a spawn signal`
              : `primary_driver = ${data.primary_driver}`}
          </div>
        )}
      </div>
    </div>
  );
}
