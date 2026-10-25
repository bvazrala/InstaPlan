import { fitColor, fitTint } from "@/lib/format";

/** Group fit badge, colored on the red → yellow → green scale. */
export default function FitPill({ fit, certainty }: { fit: number; certainty?: string }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold" style={{ background: fitTint(fit), color: fitColor(fit) }}>
      <span className="size-1.5 rounded-full" style={{ background: fitColor(fit) }} />
      {fit}% fit{certainty ? <span className="font-medium opacity-70"> · {certainty}</span> : null}
    </span>
  );
}
