"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { sortOptions } from "@/lib/sort";
import { useTrip } from "@/lib/trip-context";
import type { SortKey } from "@/lib/types";
import { OPTIONS } from "@/mocks/demo-data";
import HeatMap from "./HeatMap";
import OptionCard from "./OptionCard";

const SORTS: { id: SortKey; label: string }[] = [
  { id: "cheapest", label: "Cheapest" },
  { id: "fastest", label: "Fastest" },
  { id: "balanced", label: "Balanced" },
  { id: "fairest", label: "Fairest" },
];

/** Sort bar + option list (R12, R13). `wide` is the full trip page layout with the heat map. */
export default function OptionsView({ wide = false }: { wide?: boolean }) {
  const { sort, setSort, setStage, pick, pickedId } = useTrip();
  const [w, setW] = useState(0.5);
  const sorted = useMemo(() => sortOptions(OPTIONS, sort, w), [sort, w]);

  return (
    <div className="space-y-3">
      <div className="no-scrollbar flex gap-1.5 overflow-x-auto">
        {SORTS.map((s) => (
          <button key={s.id} onClick={() => setSort(s.id)}
            className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-semibold ${sort === s.id ? "brand-gradient text-white" : "bg-surface text-foreground"}`}>
            {s.label}
          </button>
        ))}
      </div>
      {sort === "balanced" && (
        <label className="flex items-center gap-2 text-[11px] text-muted">
          Time
          <input type="range" min={0} max={1} step={0.05} value={w} onChange={(e) => setW(Number(e.target.value))} className="flex-1 accent-[#6d3df0]" />
          Cost
        </label>
      )}

      {!wide && (
        <Link href="/trip/demo" className="flex items-center justify-between rounded-xl bg-violet-50 px-3 py-2 text-xs font-semibold text-brand">
          Open full trip page (heat map) <ExternalLink size={13} />
        </Link>
      )}
      {wide && <HeatMap options={sorted} />}

      <div className={wide ? "grid gap-3 md:grid-cols-2 xl:grid-cols-4" : "space-y-3"}>
        {sorted.map((o, i) => (
          <OptionCard key={o.id} o={o} rank={i} picked={pickedId === o.id} onPick={() => { pick(o.id); if (!wide) setStage("picked"); }} />
        ))}
      </div>
    </div>
  );
}
