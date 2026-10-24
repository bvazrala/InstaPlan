import { fitColor, fitTint } from "@/lib/format";

/** Group fit badge, colored on the red → yellow → green scale. */
export default function FitPill({ fit, certainty }: { fit: number; certainty?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold" style={{ background: fitTint(fit), color: fitColor(fit) }}>
      <span className="h-2 w-2 rounded-full" style={{ background: fitColor(fit) }} />
      {fit} fit{certainty ? <span className="font-medium opacity-70"> · {certainty}</span> : null}
    </span>
  );
}
