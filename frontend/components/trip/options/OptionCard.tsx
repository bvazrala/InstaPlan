"use client";

import { useState } from "react";
import { Check, ChevronDown, ExternalLink } from "lucide-react";
import { money } from "@/lib/format";
import { groupTotal, maxHours, perPerson, personTotal } from "@/lib/sort";
import type { Option } from "@/lib/types";
import { memberById } from "@/mocks/demo-data";
import { Avatar } from "@/components/chat/Avatar";
import { Button } from "@/components/ui/primitives";
import FitPill from "./FitPill";

/** One priced trip option with a per-person breakdown (R12). */
export default function OptionCard({ o, rank, onPick, picked }: { o: Option; rank: number; onPick: () => void; picked: boolean }) {
  const [open, setOpen] = useState(rank === 0);
  return (
    <div className={`overflow-hidden rounded-xl border bg-white shadow-xs ${picked ? "border-neutral-900" : "border-line"}`}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted">{o.place} · {o.dates}</p>
            <p className="truncate text-[17px] font-semibold leading-tight">{o.title}</p>
          </div>
          <FitPill fit={o.fit} />
        </div>
        <p className="mt-1 text-xs text-muted">{o.certainty}</p>

        <dl className="mt-4 grid grid-cols-3 divide-x divide-line text-center">
          {[["Per person", money(perPerson(o))], ["Group total", money(groupTotal(o))], ["Longest trip", `${maxHours(o)}h`]].map(([k, v]) => (
            <div key={k} className="px-1">
              <dt className="text-[11px] text-muted">{k}</dt>
              <dd className="text-[15px] font-semibold">{v}</dd>
            </div>
          ))}
        </dl>

        <button onClick={() => setOpen(!open)} aria-expanded={open} className="mt-4 flex w-full items-center justify-between border-t border-line pt-3 text-[13px] font-semibold">
          Cost breakdown <ChevronDown size={16} className={`text-muted transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="animate-in-fade mt-2">
            <p className="mb-2 text-xs text-muted">{o.lodging} · {money(o.lodgingShare)} each · about {money(o.daily)}/day for food and activities</p>
            <ul className="space-y-2">
              {o.people.map((p) => (
                <li key={p.id} className="flex items-center gap-2.5 text-[13px]">
                  <Avatar id={p.id} size={24} />
                  <span className="min-w-0 flex-1 leading-tight">
                    <span className="block font-medium">{p.id === "me" ? "You" : memberById(p.id).name}</span>
                    <span className="block text-xs text-muted">{p.origin} · {p.mode} · {p.hours}h · {money(p.cost)}</span>
                  </span>
                  <span className="font-semibold">{money(personTotal(o, p.id))}</span>
                </li>
              ))}
            </ul>
            <p className="pt-3 text-[11px] text-muted">Estimates · priced Oct 24, 9:41 AM · {o.nights} nights</p>
          </div>
        )}

        <div className="mt-4 flex gap-2">
          <Button variant={picked ? "secondary" : "default"} className="flex-1" onClick={onPick}>
            {picked ? <><Check size={15} /> Picked</> : "Pick this option"}
          </Button>
          <Button variant="outline" size="icon" aria-label="Open listing"><ExternalLink size={16} /></Button>
        </div>
      </div>
    </div>
  );
}
