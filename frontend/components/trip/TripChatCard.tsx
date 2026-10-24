"use client";

import { MapPin, Sparkles, X } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import type { Stage } from "@/lib/types";
import { FACTS, OPTIONS } from "@/mocks/demo-data";
import { money } from "@/lib/format";
import { groupTotal, perPerson } from "@/lib/sort";

const AssistantBadge = () => (
  <span className="flex items-center gap-1 text-[11px] font-semibold text-brand"><Sparkles size={12} /> Trip assistant</span>
);

/** Inline widget the planner posts into the chat; opens the trip panel (sheet on mobile). */
export default function TripChatCard() {
  const { stage, setStage, offerDismissed, dismissOffer, setPanelOpen, pickedId } = useTrip();

  const open = (s?: Stage) => { if (s) setStage(s); setPanelOpen(true); };

  if (stage === "idle") {
    if (offerDismissed) return null;
    return (
      <div className="animate-in-fade ml-9 mt-3 max-w-[300px] rounded-3xl border border-violet-100 bg-violet-50/60 p-4">
        <div className="mb-1 flex items-center justify-between">
          <AssistantBadge />
          <button onClick={dismissOffer} aria-label="Dismiss" className="text-muted"><X size={14} /></button>
        </div>
        <p className="text-[13px] font-semibold">Plan this trip?</p>
        <p className="mb-3 text-xs text-muted">Sounds like a winter break trip. I can keep track of what everyone wants as you chat.</p>
        <button onClick={() => open("collecting")} className="brand-gradient w-full rounded-xl py-2 text-sm font-semibold text-white">Plan this trip</button>
      </div>
    );
  }

  const picked = OPTIONS.find((o) => o.id === pickedId) ?? OPTIONS[0];
  const body: Record<Exclude<Stage, "idle">, { title: string; line: string; cta: string }> = {
    collecting: { title: "Trip card · live", line: `${FACTS.length} facts so far · 1 required field missing`, cta: "Open trip card" },
    voting: { title: "Are we going?", line: "Vote to lock the trip. Majority yes moves to private details.", cta: "Vote" },
    checkin: { title: "Private check-in", line: "The assistant checks in with each of you privately. Only you see yours.", cta: "Open my check-in" },
    options: { title: "4 options ready", line: "Per-person costs and group fit, sorted your way.", cta: "Compare options" },
    picked: { title: `${picked.place} · ${picked.dates}`, line: `${money(groupTotal(picked))} total · est. ${money(perPerson(picked))} each`, cta: "View summary" },
    settle: { title: "Settle up", line: "Maya paid for the rental. Pay back in one tap.", cta: "Open settle up" },
  };
  const b = body[stage];
  return (
    <div className="animate-in-fade ml-9 mt-3 max-w-[300px] rounded-3xl border border-violet-100 bg-violet-50/60 p-4">
      <div className="mb-1 flex items-center gap-1.5"><AssistantBadge /><span className="text-[11px] text-muted">· Trip Planning</span></div>
      <p className="flex items-center gap-1.5 text-[13px] font-semibold"><MapPin size={13} className="text-brand" />{b.title}</p>
      <p className="mb-3 text-xs text-muted">{b.line}</p>
      <button onClick={() => open()} className="w-full rounded-xl bg-white py-2 text-sm font-semibold text-brand ring-1 ring-violet-200">
        {b.cta}
      </button>
    </div>
  );
}
