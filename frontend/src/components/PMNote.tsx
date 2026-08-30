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

export function PMNotePanel({ data }: { data: PMNote }) {
  return (
    <section className="panel-shell lg:border-l" aria-labelledby="pm-note-title">
      <div className="panel-title-row">
        <h2 id="pm-note-title" className="panel-title">PM note</h2>
        <span className="microcopy">safe synthesis</span>
      </div>
      <div className="stack-tight">
        <span className="section-heading">Current read</span>
        <p className="font-serif text-[17px] leading-relaxed m-0">{data.current_read}</p>
      </div>
      <Bucket label="Observed" items={data.observed} treatment="solid" />
      <Bucket label="Inferred" items={data.inferred} treatment="outlined" />
      <Bucket label="Against" items={data.contradicted} treatment="inverted" />
      <Bucket label="Not confirmed" items={data.not_confirmed} treatment="dashed" />
      <div className="stack-tight">
        <span className="section-heading">What changed</span>
        <p className="note-copy whitespace-pre-wrap">{data.what_changed}</p>
      </div>
      <div className="stack-tight">
        <span className="section-heading">Next useful check</span>
        <p className="note-copy">{data.next_useful_check}</p>
      </div>
      <div className="stack-tight border-t border-line pt-4 mt-auto">
        <span className="section-heading">Citations</span>
        {data.citations.map((citation, index) => (
          <Citation key={`${citation}-${index}`} value={citation} />
        ))}
      </div>
    </section>
  );
}
