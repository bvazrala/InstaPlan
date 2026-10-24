"use client";

import { useState } from "react";
import { CircleAlert, Pencil, Sparkles } from "lucide-react";
import { FACTS, memberById } from "@/mocks/demo-data";
import { useTrip } from "@/lib/trip-context";
import { Avatar } from "@/components/chat/Avatar";
import { Card, Chip, Label, PrimaryButton } from "@/components/ui/primitives";

export default function CollectingView() {
  const { setStage } = useTrip();
  const [mode, setMode] = useState<"Fly" | "Drive" | null>(null);

  return (
    <div className="space-y-3">
      <Card className="border-violet-100 bg-violet-50/60">
        <p className="flex items-center gap-1.5 text-[11px] font-semibold text-brand"><Sparkles size={12} /> Listening to this chat</p>
        <p className="mt-1 text-xs text-muted">Facts are picked up from messages. Nobody fills out a survey.</p>
        <button className="mt-2 text-xs font-semibold text-foreground underline underline-offset-2">Stop listening</button>
      </Card>

      <div>
        <Label>What we know · {FACTS.length + (mode ? 1 : 0)}</Label>
        <ul className="space-y-2">
          {FACTS.map((f) => (
            <li key={f.id} className="flex items-center gap-3 rounded-2xl bg-surface px-3 py-2.5">
              <Avatar id={f.by} size={28} />
              <div className="min-w-0 flex-1">
                <p className="text-[11px] text-muted">{f.field} · from {memberById(f.by).name}</p>
                <p className="truncate text-[13px] font-semibold">{f.value}</p>
              </div>
              <button className="text-muted hover:text-foreground" aria-label="Edit fact"><Pencil size={14} /></button>
            </li>
          ))}
          {mode && (
            <li className="flex items-center gap-3 rounded-2xl bg-surface px-3 py-2.5">
              <Avatar id="me" size={28} />
              <div className="flex-1"><p className="text-[11px] text-muted">Travel mode · tapped by You</p><p className="text-[13px] font-semibold">{mode === "Fly" ? "Flying" : "Driving"}</p></div>
            </li>
          )}
        </ul>
      </div>

      {!mode && (
        <Card className="border-amber-200 bg-amber-50">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-amber-800"><CircleAlert size={13} /> Missing: travel mode</p>
          <p className="mb-3 text-[13px] font-semibold">Fly or drive?</p>
          <div className="flex gap-2"><Chip onClick={() => setMode("Fly")}>✈️ Fly</Chip><Chip onClick={() => setMode("Drive")}>🚗 Drive</Chip></div>
        </Card>
      )}

      <PrimaryButton onClick={() => setStage("voting")}>Ready? Call the vote</PrimaryButton>
    </div>
  );
}
