"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import { MEMBERS } from "@/mocks/demo-data";
import { useTrip } from "@/lib/trip-context";
import { Avatar } from "@/components/chat/Avatar";
import { Card, GhostButton, Label, PrimaryButton } from "@/components/ui/primitives";

type Vote = "yes" | "no" | undefined;

export default function VotingView() {
  const { setStage } = useTrip();
  const [votes, setVotes] = useState<Record<string, Vote>>({ maya: "yes", alex: "yes", sam: undefined, me: undefined });
  const yes = Object.values(votes).filter((v) => v === "yes").length;
  const majority = yes > MEMBERS.length / 2;

  return (
    <div className="space-y-3">
      <Card className="text-center">
        <p className="text-base font-bold">We&apos;re going?</p>
        <p className="mt-0.5 text-xs text-muted">New York City · Dec 18 – 21 · 4 people</p>
        <div className="mt-3 flex gap-2">
          <PrimaryButton onClick={() => setVotes((v) => ({ ...v, me: "yes" }))}>Yes, we&apos;re going</PrimaryButton>
          <GhostButton onClick={() => setVotes((v) => ({ ...v, me: "no" }))}>Not yet</GhostButton>
        </div>
      </Card>

      <div>
        <Label>{yes} of {MEMBERS.length} in</Label>
        <div className="mb-3 h-2 overflow-hidden rounded-full bg-surface"><div className="brand-gradient h-full transition-all" style={{ width: `${(yes / MEMBERS.length) * 100}%` }} /></div>
        <ul className="space-y-1.5">
          {MEMBERS.map((m) => (
            <li key={m.id} className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2">
              <Avatar id={m.id} size={26} />
              <span className="flex-1 text-[13px] font-semibold">{m.name}</span>
              {votes[m.id] === "yes" && <Check size={16} className="text-emerald-600" />}
              {votes[m.id] === "no" && <X size={16} className="text-red-500" />}
              {!votes[m.id] && <span className="text-[11px] text-muted">waiting</span>}
            </li>
          ))}
        </ul>
      </div>

      {majority ? (
        <PrimaryButton onClick={() => setStage("checkin")}>Majority yes · lock it in</PrimaryButton>
      ) : (
        <p className="text-center text-xs text-muted">Needs a majority to lock the trip.</p>
      )}
      <button onClick={() => setStage("collecting")} className="w-full text-center text-xs font-semibold text-muted underline underline-offset-2">Back to collecting</button>
    </div>
  );
}
