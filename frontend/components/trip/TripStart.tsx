"use client";

import { X } from "lucide-react";
import { memberById } from "@/mocks/demo-data";
import { displayName } from "@/lib/trip-model";
import { useTrip } from "@/lib/trip-context";
import { Avatar } from "@/components/chat/Avatar";
import { CHAT_META } from "@/components/chat/chat-meta";
import { PrimaryButton } from "@/components/ui/primitives";

const STEPS = [
  ["Add details", "Destination, dates, where everyone is travelling from, diet and more, picked up from the chat."],
  ["Vote", "Say who's in. Anyone who stays quiet or taps Not going isn't part of the plan."],
  ["Check in", "Review everyone's details, then add your budget privately."],
  ["Compare options", "Costs per person and how well each fits the group."],
  ["Log expenses", "Everyone adds what they paid. The final cost per person comes after."],
  ["Finalize", "More than half of the group accepts, then payments open."],
];

/** Empty state of the trip panel, before anyone has started planning. */
export default function TripStart({ onClose }: { onClose?: () => void }) {
  const { setStage, members } = useTrip();
  return (
    <div className="pb-8">
      <header className="flex h-[68px] items-center justify-between border-b border-line px-5">
        <h2 className="text-[17px] font-semibold">Trip planner</h2>
        {onClose && <button onClick={onClose} aria-label="Close" className="flex size-9 items-center justify-center rounded-full transition hover:bg-surface"><X size={20} /></button>}
      </header>

      <div className="px-5 pt-6">
        <h3 className="text-xl font-bold tracking-tight">Plan a trip with the group</h3>
        <p className="mt-1 text-sm leading-snug text-muted">The assistant reads the chat for trip details, then checks in with each person privately.</p>
        <PrimaryButton onClick={() => setStage("collecting")} className="mt-4">Start planning</PrimaryButton>

        <ol className="mt-7 space-y-4">
          {STEPS.map(([title, sub], i) => (
            <li key={title} className="flex gap-3.5">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-line text-[13px] font-semibold">{i + 1}</span>
              <span className="leading-snug">
                <span className="block text-[15px] font-semibold">{title}</span>
                <span className="block text-[13px] text-muted">{sub}</span>
              </span>
            </li>
          ))}
        </ol>

        <h3 className="mb-1 mt-8 text-[13px] font-semibold text-muted">In this chat</h3>
        <ul>
          {members.map((id) => (
            <li key={id} className="flex items-center gap-3 py-2">
              <Avatar id={id} size={40} online={!!CHAT_META[id]?.online} />
              <span className="min-w-0 leading-tight">
                <span className="block truncate text-[15px] font-medium">{displayName(id)}</span>
                <span className="block truncate text-[13px] text-muted">{memberById(id).handle}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
