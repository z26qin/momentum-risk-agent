import type { MechanismStatus, RiskState } from "../data/types";

const STATUS_STYLE: Record<MechanismStatus, string> = {
  triggered: "bg-amber text-bg border-amber",
  watch: "text-amber border-amber",
  not_confirmed: "text-muted border-line border-dashed",
  unavailable: "text-muted border-line border-dotted",
};

function formatMetric(value: number | null): string {
  return value === null ? "unavailable" : value.toFixed(3);
}

export function RiskStatePanel({ data }: { data: RiskState }) {
  const severityPosition = `${data.severity.score ?? 0}%`;
  const mechanismEntries = Object.entries(data.mechanisms) as Array<
    [string, MechanismStatus]
  >;

  return (
    <section className="panel-shell lg:border-r" aria-labelledby="risk-state-title">
      <div className="panel-title-row">
        <h2 id="risk-state-title" className="panel-title">RiskState</h2>
        <span className="microcopy">immutable · code-owned</span>
      </div>

      <div className="stack">
        <div className="section-heading-row">
          <span className="section-heading">Deterministic signals</span>
          <span className="mono-value">
            {data.monitoring_trigger_count} / {data.total_signal_count}
          </span>
        </div>
        <div className="tag-list">
          {data.triggered_signals.length ? data.triggered_signals.map((signal) => (
            <span key={signal} className="tag tag-hot">{signal}</span>
          )) : <span className="empty-copy">No triggered signals</span>}
        </div>
        <div className="tag-list">
          {data.structural_flags.map((flag) => (
            <span key={flag} className="tag">structural · {flag}</span>
          ))}
        </div>
      </div>

      <div className="stack">
        <span className="section-heading">Mechanism status</span>
        {mechanismEntries.map(([name, status]) => (
          <div key={name} className="mechanism-row">
            <span className="mono-value break-all">{name}</span>
            <span className={`status-chip ${STATUS_STYLE[status]}`}>{status}</span>
          </div>
        ))}
        {data.theme_cluster.length > 0 && (
          <div className="tag-list">
            {data.theme_cluster.map((symbol) => (
              <span key={symbol} className="tag tag-hot">{symbol}</span>
            ))}
          </div>
        )}
      </div>

      <div className="stack">
        <span className="section-heading">Book metrics</span>
        {Object.entries(data.book).map(([name, value]) => (
          <div key={name} className="metric-row">
            <span>{name}</span><span>{formatMetric(value)}</span>
          </div>
        ))}
      </div>

      <div className="stack mt-auto">
        <div className="section-heading-row">
          <span className="section-heading">Relative severity</span>
          <span className="microcopy">not a probability</span>
        </div>
        <div className="severity-track" aria-label={`Relative severity ${data.severity.score ?? "unavailable"}`}>
          <span className="severity-marker" style={{ left: severityPosition }} />
        </div>
        <div className="section-heading-row">
          <span className="mono-value">{data.severity.label}</span>
          <span className="mono-value">{data.severity.score ?? "—"} / 100</span>
        </div>
        <p className="microcopy m-0">driver · {data.severity.primary_driver}</p>
        <p className="microcopy m-0">state · {data.mechanical_unwind_state}</p>
      </div>
    </section>
  );
}
