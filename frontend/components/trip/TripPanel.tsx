"use client";

import { X } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import type { Stage } from "@/lib/types";
import { Badge, Button } from "@/components/ui/primitives";
import CollectingView from "./CollectingView";
import VotingView from "./VotingView";
import CheckInView from "./CheckInView";
import OptionsView from "./options/OptionsView";
import ExpensesView from "./ExpensesView";
import SummaryView from "./SummaryView";
import FinalizeView from "./FinalizeView";
import SettleView from "./SettleView";
import ParticipationBar from "./ParticipationBar";

const STEPS: { id: Exclude<Stage, "idle">; label: string }[] = [
  { id: "collecting", label: "Details" },
  { id: "voting", label: "Vote" },
  { id: "checkin", label: "Check-in" },
  { id: "options", label: "Options" },
  { id: "expenses", label: "Expenses" },
  { id: "picked", label: "Cost" },
  { id: "finalize", label: "Finalize" },
  { id: "settle", label: "Payments" },
];

export default function TripPanel({ onClose }: { onClose?: () => void }) {
  const { stage, setStage, profile, participants, finalized } = useTrip();
  const dest = profile.group.destination?.value;
  const dates = profile.group.dates?.value;

  return (
    <div>
      <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-line bg-white px-5">
        <div className="min-w-0 leading-tight">
          <p className="flex items-center gap-2 text-base font-semibold">
            <span className="truncate">{dest ? `Trip to ${dest}` : "New trip"}</span>
            {finalized && <Badge variant="success">Finalized</Badge>}
          </p>
          <p className="text-xs text-muted">{dates ?? "Dates not set"} · {participants.length} going</p>
        </div>
        {onClose && <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close"><X size={18} /></Button>}
      </header>

      <nav className="no-scrollbar sticky top-[68px] z-10 overflow-x-auto border-b border-line bg-white px-5 py-2.5" aria-label="Trip steps">
        <div className="inline-flex h-9 items-center rounded-lg bg-neutral-100 p-[3px]">
          {STEPS.map((s) => {
            const active = s.id === stage;
            return (
              <button
                key={s.id}
                ref={(el) => { if (active && el) el.scrollIntoView({ inline: "center", block: "nearest" }); }}
                onClick={() => setStage(s.id)}
                aria-current={active ? "step" : undefined}
                className={`h-full whitespace-nowrap rounded-md px-3 text-[13px] font-medium transition ${active ? "bg-white text-neutral-900 shadow-sm" : "text-neutral-500 hover:text-neutral-900"}`}
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </nav>

      <ParticipationBar />

      <div key={stage} className="animate-in-fade p-5">
        {stage === "collecting" && <CollectingView />}
        {stage === "voting" && <VotingView />}
        {stage === "checkin" && <CheckInView />}
        {stage === "options" && <OptionsView />}
        {stage === "expenses" && <ExpensesView />}
        {stage === "picked" && <SummaryView />}
        {stage === "finalize" && <FinalizeView />}
        {stage === "settle" && <SettleView />}
      </div>
    </div>
  );
}
