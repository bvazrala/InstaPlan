"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import { sortOptions } from "@/lib/sort";
import { useTrip } from "@/lib/trip-context";
import type { SortKey } from "@/lib/types";
import { OPTIONS } from "@/mocks/demo-data";
import { Button, inputCls, Segmented } from "@/components/ui/primitives";
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
  const { sort, setSort, setStage, pick, pickedId, trip, update } = useTrip();
  const [ask, setAsk] = useState("");
  const request = () => { const t = ask.trim(); if (!t) return; update((s) => ({ requests: [...s.requests, t] })); setAsk(""); };
  const [w, setW] = useState(0.5);
  const sorted = useMemo(() => sortOptions(OPTIONS, sort, w), [sort, w]);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold tracking-tight">{OPTIONS.length} options</h3>
        <p className="mb-3 text-sm text-muted">Priced per person for the whole group.</p>
        <Segmented<SortKey> value={sort} onChange={setSort} options={SORTS} />
      </div>
      {sort === "balanced" && (
        <label className="flex items-center gap-3 text-xs font-medium text-muted">
          Time
          <input type="range" min={0} max={1} step={0.05} value={w} onChange={(e) => setW(Number(e.target.value))} className="flex-1 accent-[#6d3df0]" aria-label="Balance time and cost" />
          Cost
        </label>
      )}

      {!wide && (
        <div>
          <div className="flex gap-2">
            <input value={ask} onChange={(e) => setAsk(e.target.value)} onKeyDown={(e) => e.key === "Enter" && request()} placeholder="Ask for a change, like cheaper lodging" className={inputCls} aria-label="Ask for a change" />
            <Button variant="outline" onClick={request} disabled={!ask.trim()}>Send</Button>
          </div>
          {trip.requests.length > 0 && (
            <ul className="mt-2 space-y-1">{trip.requests.map((r, i) => <li key={i} className="text-xs text-muted">Asked: {r}</li>)}</ul>
          )}
        </div>
      )}

      {!wide && (
        <Link href="/trip/demo" className="flex items-center justify-between rounded-lg border border-line px-4 py-2.5 text-[13px] font-medium shadow-xs transition hover:bg-neutral-50">
          Compare side by side <ChevronRight size={16} className="text-muted" />
        </Link>
      )}
      {wide && <HeatMap options={sorted} />}

      <div className={wide ? "grid gap-3 md:grid-cols-2 xl:grid-cols-4" : "space-y-3"}>
        {sorted.map((o, i) => (
          <OptionCard key={o.id} o={o} rank={i} picked={pickedId === o.id} onPick={() => { pick(o.id); if (!wide) setStage("expenses"); }} />
        ))}
      </div>
    </div>
  );
}
