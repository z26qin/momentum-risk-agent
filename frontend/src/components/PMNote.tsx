import type { PMNote as PMNoteData } from "../data/types";

/**
 * The four evidence categories get four distinct visual treatments.
 * This taxonomy IS the design system:
 *   observed    = solid / high-contrast
 *   inferred    = outlined with italic label
 *   against     = inverted
 *   not confirmed = dashed border, desaturated
 */

function Bullet({ fill }: { fill: "solid" | "outlined" | "inverted" | "dashed" }) {
  const styles: Record<typeof fill, string> = {
    solid: "w-[7px] h-[7px] bg-ink shrink-0 mt-[7px]",
    outlined: "w-[7px] h-[7px] border border-ink shrink-0 mt-[7px]",
    inverted: "w-[7px] h-[7px] bg-bg shrink-0 mt-[7px]",
    dashed: "w-[7px] h-[7px] border border-dashed border-muted shrink-0 mt-[7px]",
  };
  return <div className={styles[fill]} />;
}

function parseCitation(raw: string): { id: string; text: string } {
  const match = raw.match(/^\[([^\]]+)\]\s*(.*)$/);
  if (match) return { id: match[1], text: match[2] };
  return { id: "", text: raw };
}

export function PMNotePanel({ data }: { data: PMNoteData }) {
  return (
    <div className="w-full lg:w-[420px] shrink-0 lg:border-l border-line bg-panel p-5 pb-7 flex flex-col gap-4 box-border">
      <div className="flex items-baseline justify-between">
        <h2 className="font-grot text-[11px] font-semibold tracking-[0.16em] uppercase text-ink m-0">
          PM note
        </h2>
        <span className="font-mono text-[10px] text-muted">code synthesis</span>
      </div>

      {/* Current read */}
      <div className="flex flex-col gap-2">
        <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
          Current read
        </span>
        <p className="font-serif text-[17px] leading-relaxed text-ink m-0">
          {data.current_read}
        </p>
      </div>

      {/* OBSERVED — solid, high contrast */}
      <div className="flex flex-col gap-2">
        <span className="font-grot text-[10px] font-semibold tracking-[0.14em] uppercase text-ink">
          Observed
        </span>
        <div className="flex flex-col gap-1.5">
          {data.observed.map((item, i) => (
            <div key={i} className="flex gap-2.5 items-start">
              <Bullet fill="solid" />
              <span className="font-serif text-sm leading-relaxed text-ink">
                {item}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* INFERRED — outlined, italic label */}
      <div className="flex flex-col gap-2">
        <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted italic">
          Inferred
        </span>
        <div className="border border-line p-2.5 flex flex-col gap-1.5">
          {data.inferred.map((item, i) => (
            <div key={i} className="flex gap-2.5 items-start">
              <Bullet fill="outlined" />
              <span className="font-serif text-sm leading-relaxed text-ink">
                {item}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* AGAINST — inverted */}
      <div className="flex flex-col gap-2">
        <span className="font-grot text-[10px] font-semibold tracking-[0.14em] uppercase bg-ink text-bg px-2 py-0.5 self-start">
          Against
        </span>
        <div className="bg-ink p-2.5 flex flex-col gap-1.5">
          {data.against.map((item, i) => (
            <div key={i} className="flex gap-2.5 items-start">
              <Bullet fill="inverted" />
              <span className="font-serif text-sm leading-relaxed text-bg">
                {item}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* NOT CONFIRMED — dashed, desaturated */}
      <div className="flex flex-col gap-2">
        <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
          Not confirmed
        </span>
        <div className="border border-dashed border-line p-2.5 flex flex-col gap-1.5">
          {data.not_confirmed.map((item, i) => (
            <div key={i} className="flex gap-2.5 items-start">
              <Bullet fill="dashed" />
              <span className="font-serif text-sm leading-relaxed text-muted">
                {item}
              </span>
            </div>
          ))}
        </div>
      </div>

      {data.what_changed && (
        <div className="flex flex-col gap-2">
          <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
            What changed
          </span>
          <p className="font-serif text-sm leading-relaxed text-ink m-0 whitespace-pre-wrap">
            {data.what_changed}
          </p>
        </div>
      )}

      {data.next_useful_check && (
        <div className="flex flex-col gap-2">
          <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
            Next useful check
          </span>
          <p className="font-serif text-sm leading-relaxed text-ink m-0">
            {data.next_useful_check}
          </p>
        </div>
      )}

      {/* Citations */}
      <div className="flex flex-col gap-2 mt-auto pt-3.5 border-t border-line">
        <span className="font-grot text-[10px] tracking-[0.14em] uppercase text-muted">
          Citations
        </span>
        <div className="flex flex-col gap-1">
          {data.citations.length === 0 && (
            <span className="font-mono text-[10px] text-muted">None</span>
          )}
          {data.citations.map((raw, i) => {
            const { id, text } = parseCitation(raw);
            return (
              <div key={i} className="flex gap-2 items-baseline">
                {id && (
                  <span className="font-mono text-[10px] text-amber shrink-0">
                    [{id}]
                  </span>
                )}
                <span className="font-mono text-[10px] text-muted leading-relaxed">
                  {text}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
