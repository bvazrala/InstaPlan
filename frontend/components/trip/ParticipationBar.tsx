"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import { displayName } from "@/lib/trip-model";
import { Avatar, AvatarStack } from "@/components/chat/Avatar";
import { Badge, Button } from "@/components/ui/primitives";

/** Slim strip under the step tabs: who is in the plan, and your own in/out switch. Expands for the full list. */
export default function ParticipationBar() {
  const { participants, inactive, optOut, join } = useTrip();
  const [open, setOpen] = useState(false);
  const going = participants.includes("me");

  return (
    <div className="border-b border-line">
      <div className="flex items-center gap-3 px-5 py-2.5">
        <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex min-w-0 flex-1 items-center gap-2.5 text-left">
          <AvatarStack ids={participants.slice(0, 4)} size={24} />
          <span className="min-w-0 truncate text-[13px] font-medium">
            {participants.length} going
            {inactive.length > 0 && <span className="font-normal text-muted"> · {inactive.length} not included</span>}
          </span>
          <ChevronDown size={14} className={`shrink-0 text-muted transition ${open ? "rotate-180" : ""}`} />
        </button>
        {going ? (
          <Button size="sm" variant="outline" onClick={optOut}>Not going</Button>
        ) : (
          <Button size="sm" onClick={join}>I&apos;m in</Button>
        )}
      </div>

      {open && (
        <div className="animate-in-fade space-y-3 px-5 pb-4">
          <p className="text-xs leading-snug text-muted">You&apos;re in the plan once you&apos;ve spoken in the chat about it and haven&apos;t tapped Not going.</p>
          <ul className="divide-y divide-line rounded-lg border border-line">
            {participants.map((id) => (
              <li key={id} className="flex items-center gap-2.5 px-3 py-2">
                <Avatar id={id} size={24} />
                <span className="flex-1 text-[13px] font-medium">{displayName(id)}</span>
                <Badge variant="success">Going</Badge>
              </li>
            ))}
            {inactive.map((p) => (
              <li key={p.id} className="flex items-center gap-2.5 px-3 py-2">
                <Avatar id={p.id} size={24} />
                <span className="flex-1 text-[13px] font-medium text-neutral-500">{displayName(p.id)}</span>
                <Badge variant="outline">{p.reason}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
