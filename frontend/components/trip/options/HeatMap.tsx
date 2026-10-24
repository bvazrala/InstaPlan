import { fitColor } from "@/lib/format";
import { CATEGORIES, type Option } from "@/lib/types";

/** Options × categories grid of group fit scores (R14). Shown on the full trip page. */
export default function HeatMap({ options }: { options: Option[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-line">
      <table className="w-full min-w-[420px] border-collapse text-xs">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wider text-muted">
            <th className="p-2.5 font-semibold">Option</th>
            {CATEGORIES.map((c) => <th key={c} className="p-2.5 text-center font-semibold">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {options.map((o) => (
            <tr key={o.id} className="border-t border-line">
              <td className="p-2.5 font-semibold">{o.title}</td>
              {CATEGORIES.map((c) => (
                <td key={c} className="p-1.5">
                  <div className="rounded-lg py-2 text-center font-bold" style={{ background: fitColor(o.cats[c], 0.9), color: "white" }}>{o.cats[c]}</div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
