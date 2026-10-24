"use client";

import { ArrowLeft, XCircle } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import type { Stage } from "@/lib/types";
import CollectingView from "./CollectingView";
import VotingView from "./VotingView";
import PrivateCheckIn from "@/components/private/PrivateCheckIn";
import OptionsView from "./options/OptionsView";
import SummaryView from "./SummaryView";
import SettleView from "./SettleView";

const STEPS: { id: Exclude<Stage, "idle">; label: string }[] = [
  { id: "collecting", label: "Collect" },
  { id: "voting", label: "Vote" },
  { id: "checkin", label: "Check-in" },
  { id: "options", label: "Options" },
  { id: "picked", label: "Summary" },
  { id: "settle", label: "Settle up" },
];

export default function TripPanel({ onClose }: { onClose?: () => void }) {
  const { stage, setStage } = useTrip();
  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <button onClick={() => setStage("idle")} className="flex items-center gap-1.5 text-[15px] font-semibold">
          <ArrowLeft size={16} /> Trip Planning
        </button>
        <button onClick={() => { setStage("idle"); onClose?.(); }} aria-label="Close" className="text-foreground"><XCircle size={20} /></button>
      </div>

      {/* Demo stage jumper: lets teammates and judges hop between steps. */}
      <div className="no-scrollbar -mx-1 mb-4 flex gap-1.5 overflow-x-auto px-1">
        {STEPS.map((s, i) => {
          const active = s.id === stage;
          return (
            <button key={s.id} onClick={() => setStage(s.id)}
              className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${active ? "brand-gradient text-white" : "bg-surface text-muted hover:bg-neutral-100"}`}>
              {i + 1} · {s.label}
            </button>
          );
        })}
      </div>

      <div key={stage} className="animate-in-fade">
        {stage === "collecting" && <CollectingView />}
        {stage === "voting" && <VotingView />}
        {stage === "checkin" && <PrivateCheckIn />}
        {stage === "options" && <OptionsView />}
        {stage === "picked" && <SummaryView />}
        {stage === "settle" && <SettleView />}
      </div>
    </div>
  );
}
