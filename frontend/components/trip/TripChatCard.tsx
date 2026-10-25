"use client";

import { Compass, X } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import type { Stage } from "@/lib/types";
import { OPTIONS } from "@/mocks/demo-data";
import { money } from "@/lib/format";
import { displayName, filledFields, totalFields } from "@/lib/trip-model";
import { totalOf } from "@/lib/expenses";

const Sender = () => (
  <span className="flex items-center gap-1.5 text-xs font-semibold text-muted">
    <span className="flex size-5 items-center justify-center rounded-full bg-brand text-white"><Compass size={12} /></span> Trip assistant
  </span>
);

/** Inline card the assistant posts into the chat; every line is read from this trip's state. */
export default function TripChatCard() {
  const { trip, stage, setStage, offerDismissed, dismissOffer, setPanelOpen, participants, profile, need, accepted, finalized } = useTrip();
  const open = (s?: Stage) => { if (s) setStage(s); setPanelOpen(true); };

  if (stage === "idle") {
    if (offerDismissed) return null;
    return (
      <div className="animate-in-fade ml-9 mt-3 max-w-[300px] rounded-2xl border border-line bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <Sender />
          <button onClick={dismissOffer} aria-label="Dismiss" className="text-muted hover:text-foreground"><X size={15} /></button>
        </div>
        <p className="text-[15px] font-semibold">Plan this trip?</p>
        <p className="mb-3 text-[13px] leading-snug text-muted">I can keep track of what everyone wants as you chat.</p>
        <button onClick={() => open("collecting")} className="h-9 w-full rounded-md bg-neutral-900 text-sm font-medium text-white transition hover:bg-neutral-800 active:scale-[.98]">Start planning</button>
      </div>
    );
  }

  const yes = participants.filter((id) => trip.votes[id] === "yes").length;
  const done = participants.filter((id) => trip.expensesDone.includes(id)).length;
  const last = trip.expenses.at(-1);
  const body: Record<Exclude<Stage, "idle">, { title: string; line: string; cta: string }> = {
    collecting: { title: "Trip details", line: `${filledFields(profile, participants)} of ${totalFields(participants)} details filled in from the chat`, cta: "View details" },
    voting: { title: "Are we going?", line: `${yes} of ${participants.length} are in so far.`, cta: "Vote" },
    checkin: { title: "Check-in", line: `${trip.checkedIn.filter((id) => participants.includes(id)).length} of ${participants.length} have submitted. Your answers stay private.`, cta: "Open check-in" },
    options: { title: `${OPTIONS.length} options ready`, line: "Costs per person and group fit.", cta: "Compare options" },
    expenses: { title: "Expenses", line: `${done} of ${participants.length} have finished adding what they paid.`, cta: "Add expenses" },
    picked: { title: "Final cost", line: done === participants.length ? `${money(totalOf(trip.expenses))} total across ${participants.length} people.` : `Ready once everyone finishes adding expenses (${done} of ${participants.length}).`, cta: "View final cost" },
    finalize: { title: "Finalize trip", line: finalized ? "The group accepted the plan." : `${accepted} of ${need} needed have accepted.`, cta: finalized ? "View plan" : "Review and accept" },
    settle: {
      title: "Payments",
      line: !finalized ? "Open once the trip is finalized." : last ? `${displayName(last.payer)} paid ${money(last.amount)} for ${last.what}.` : "No expenses were logged.",
      cta: "Open payments",
    },
  };
  const b = body[stage];
  return (
    <div className="animate-in-fade ml-9 mt-3 max-w-[300px] rounded-2xl border border-line bg-white p-4">
      <div className="mb-2"><Sender /></div>
      <p className="text-[15px] font-semibold">{b.title}</p>
      <p className="mb-3 text-[13px] leading-snug text-muted">{b.line}</p>
      <button onClick={() => open()} className="h-9 w-full rounded-md border border-line bg-white text-sm font-medium shadow-xs transition hover:bg-neutral-50 active:scale-[.98]">{b.cta}</button>
    </div>
  );
}
