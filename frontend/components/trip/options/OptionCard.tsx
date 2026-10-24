"use client";

import { useState } from "react";
import { ChevronDown, Clock, ExternalLink } from "lucide-react";
import { fitColor, money } from "@/lib/format";
import { groupTotal, maxHours, perPerson, personTotal } from "@/lib/sort";
import type { Option } from "@/lib/types";
import { memberById } from "@/mocks/demo-data";
import { Avatar } from "@/components/chat/Avatar";
import { PrimaryButton } from "@/components/ui/primitives";
import FitPill from "./FitPill";

/** One priced trip option with a per-person breakdown (R12). */
export default function OptionCard({ o, rank, onPick, picked }: { o: Option; rank: number; onPick: () => void; picked: boolean }) {
  const [open, setOpen] = useState(rank === 0);
  const total = groupTotal(o);
  return (
    <div className={`overflow-hidden rounded-2xl border bg-white ${picked ? "border-violet-300 ring-2 ring-violet-100" : "border-line"}`}>
      <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${fitColor(o.fit)}, ${fitColor(Math.min(100, o.fit + 15), 0.5)})` }} />
      <div className="p-3.5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-[11px] text-muted">#{rank + 1} · {o.place} · {o.dates}</p>
            <p className="text-[15px] font-bold leading-tight">{o.title}</p>
          </div>
          <FitPill fit={o.fit} />
        </div>
        <p className="mt-0.5 text-[11px] text-muted">{o.certainty}</p>

        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {[["Per person", money(perPerson(o))], ["Group total", money(total)], ["Longest trip", `${maxHours(o)}h`]].map(([k, v]) => (
            <div key={k} className="rounded-xl bg-surface py-2"><p className="text-[10px] text-muted">{k}</p><p className="text-[13px] font-bold">{v}</p></div>
          ))}
        </div>

        <button onClick={() => setOpen(!open)} className="mt-3 flex w-full items-center justify-between text-xs font-semibold text-muted">
          Breakdown <ChevronDown size={14} className={`transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="mt-2 space-y-1.5 animate-in-fade">
            <p className="text-[11px] text-muted">🏠 {o.lodging} · {money(o.lodgingShare)} each · 🍽 ~{money(o.daily)}/day est.</p>
            {o.people.map((p) => (
              <div key={p.id} className="flex items-center gap-2 text-xs">
                <Avatar id={p.id} size={20} />
                <span className="w-12 font-semibold">{memberById(p.id).name}</span>
                <span className="flex-1 text-muted">{p.origin} · {p.mode} · <Clock size={10} className="inline" /> {p.hours}h · {money(p.cost)}</span>
                <span className="font-bold">{money(personTotal(o, p.id))}</span>
              </div>
            ))}
            <p className="pt-1 text-[10px] text-muted">Estimates · prices as of Oct 24, 9:41 AM · {o.nights} nights</p>
          </div>
        )}

        <div className="mt-3 flex gap-2">
          <PrimaryButton onClick={onPick}>{picked ? "Picked ✓" : "Pick this one"}</PrimaryButton>
          <button className="flex w-11 shrink-0 items-center justify-center rounded-xl bg-surface" aria-label="Open listing"><ExternalLink size={15} /></button>
        </div>
      </div>
    </div>
  );
}
