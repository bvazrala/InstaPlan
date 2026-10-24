"use client";

import { useState } from "react";
import { Share2, Wand2 } from "lucide-react";
import { MEMBERS, OPTIONS } from "@/mocks/demo-data";
import { money } from "@/lib/format";
import { groupTotal, perPerson, personTotal } from "@/lib/sort";
import { useTrip } from "@/lib/trip-context";
import { Avatar } from "@/components/chat/Avatar";
import { Card, GhostButton, Label, PrimaryButton } from "@/components/ui/primitives";

export default function SummaryView() {
  const { pickedId, setStage } = useTrip();
  const o = OPTIONS.find((x) => x.id === pickedId) ?? OPTIONS[0];
  const [tweak, setTweak] = useState("");

  return (
    <div className="space-y-3">
      {/* Placeholder for the Muse Image trip poster */}
      <div className="relative flex h-36 items-end overflow-hidden rounded-2xl bg-gradient-to-br from-violet-500 via-fuchsia-500 to-orange-400 p-4 text-white">
        <div className="absolute right-3 top-3 rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-semibold backdrop-blur">Muse poster</div>
        <div>
          <p className="text-xs font-semibold opacity-90">{o.dates}</p>
          <p className="text-xl font-extrabold leading-tight">{o.place}</p>
          <p className="text-xs opacity-90">{o.title}</p>
        </div>
      </div>

      <Card>
        <div className="flex items-end justify-between">
          <div><p className="text-[11px] text-muted">Group total (est.)</p><p className="text-2xl font-extrabold">{money(groupTotal(o))}</p></div>
          <div className="text-right"><p className="text-[11px] text-muted">Per person</p><p className="text-lg font-bold">{money(perPerson(o))}</p></div>
        </div>
      </Card>

      <div>
        <Label>Each person</Label>
        <ul className="space-y-1.5">
          {MEMBERS.map((m) => (
            <li key={m.id} className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2 text-[13px]">
              <Avatar id={m.id} size={24} /><span className="flex-1 font-semibold">{m.name}</span><span className="font-bold">{money(personTotal(o, m.id))}</span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <Label>Tweak in plain words</Label>
        <div className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2">
          <Wand2 size={15} className="text-brand" />
          <input value={tweak} onChange={(e) => setTweak(e.target.value)} placeholder='e.g. "cheaper lodging"' className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted" />
          <button onClick={() => { setTweak(""); setStage("options"); }} className="text-xs font-semibold text-brand">Re-run</button>
        </div>
      </div>

      <div className="flex gap-2">
        <GhostButton onClick={() => setStage("options")}>Change pick</GhostButton>
        <PrimaryButton onClick={() => setStage("settle")}>Settle up</PrimaryButton>
      </div>
      <button className="flex w-full items-center justify-center gap-1.5 text-xs font-semibold text-muted"><Share2 size={13} /> Share summary to chat</button>
    </div>
  );
}
