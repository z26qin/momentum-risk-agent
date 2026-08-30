import type { NotePhase } from "../data/playback";
import type { PMNote } from "../data/types";

function Bucket({
  label,
  items,
  treatment,
}: {
  label: string;
  items: string[];
  treatment: "solid" | "outlined" | "inverted" | "dashed";
}) {
  return (
    <div className="stack-tight">
      <span className={`bucket-label bucket-label-${treatment}`}>{label}</span>
      <div className={`bucket bucket-${treatment}`}>
        {items.map((item, index) => (
          <div key={`${label}-${index}`} className="bucket-item">
            <span className={`bucket-dot bucket-dot-${treatment}`} />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Citation({ value }: { value: string }) {
  const match = value.match(/^\[([^\]]+)\]\s*(.*)$/);
  return (
    <div className="citation">
      {match ? <><span className="text-amber">[{match[1]}]</span><span>{match[2]}</span></> : <span>{value}</span>}
    </div>
  );
}

export function PMNotePanel({ data, phase }: { data: PMNote; phase: NotePhase }) {
  const complete = phase === "complete";
  return (
    <section className="panel-shell lg:border-l" aria-labelledby="pm-note-title">
      <div className="panel-title-row">
        <h2 id="pm-note-title" className="panel-title">PM note</h2>
        <span className="microcopy">{complete ? "safe synthesis" : "waiting for combined stop"}</span>
      </div>
      <div className="stack-tight">
        <span className="section-heading">Current read</span>
        <p className="font-serif text-[17px] leading-relaxed m-0">
          {complete ? data.current_read : phase === "pending"
            ? "RiskState is frozen. The orchestrator has not routed yet."
            : "The bounded specialist loop is still running; synthesis waits for COMBINED STOP."}
        </p>
      </div>
      <Bucket label="Observed" items={complete ? data.observed : ["Awaiting calibrated synthesis."]} treatment="solid" />
      <Bucket label="Inferred" items={complete ? data.inferred : ["Pending"]} treatment="outlined" />
      <Bucket label="Against" items={complete ? data.contradicted : ["Pending"]} treatment="inverted" />
      <Bucket label="Not confirmed" items={complete ? data.not_confirmed : ["Pending"]} treatment="dashed" />
      <div className="stack-tight">
        <span className="section-heading">What changed</span>
        <p className="note-copy whitespace-pre-wrap">{complete ? data.what_changed : "Pending"}</p>
      </div>
      <div className="stack-tight">
        <span className="section-heading">Next useful check</span>
        <p className="note-copy">{complete ? data.next_useful_check : "Pending"}</p>
      </div>
      <div className="stack-tight border-t border-line pt-4 mt-auto">
        <span className="section-heading">Citations</span>
        {(complete ? data.citations : ["Pending"]).map((citation, index) => (
          <Citation key={`${citation}-${index}`} value={citation} />
        ))}
      </div>
    </section>
  );
}
