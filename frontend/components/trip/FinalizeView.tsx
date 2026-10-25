"use client";

import { CircleCheck } from "lucide-react";
import { OPTIONS } from "@/mocks/demo-data";
import { money } from "@/lib/format";
import { totalOf } from "@/lib/expenses";
import { displayName } from "@/lib/trip-model";
import { useTrip } from "@/lib/trip-context";
import { Avatar, AvatarStack } from "@/components/chat/Avatar";
import { Badge, Button, Progress } from "@/components/ui/primitives";

/** Step 7: the group accepts the plan. More than half of the people going must accept for it to be final. */
export default function FinalizeView() {
  const { trip, participants, pickedId, profile, update, setStage, need, accepted, finalized } = useTrip();
  const o = OPTIONS.find((x) => x.id === pickedId);
  const going = participants.includes("me");
  const mine = trip.accepts.includes("me");
  const total = totalOf(trip.expenses);

  const rows: [string, string][] = [
    ["Destination", o?.place ?? profile.group.destination?.value ?? "Not set"],
    ["Dates", o?.dates ?? profile.group.dates?.value ?? "Not set"],
    ["Stay", o ? `${o.title} · ${o.lodging}` : "No option picked"],
    ["Total cost", money(total)],
    ["Average each", money(participants.length ? total / participants.length : 0)],
  ];

  return (
    <div>
      <h3 className="text-lg font-semibold tracking-tight">Finalize trip</h3>
      <p className="mt-0.5 text-[13px] leading-snug text-muted">Accept the plan below. It&apos;s final once more than half of the people going accept.</p>

      <div className="mt-4 rounded-xl border border-line p-4 shadow-xs">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Plan</p>
          <AvatarStack ids={participants.slice(0, 5)} size={22} />
        </div>
        <dl className="mt-3 divide-y divide-line">
          {rows.map(([k, v]) => (
            <div key={k} className="flex items-baseline justify-between gap-4 py-2 text-sm"><dt className="text-muted">{k}</dt><dd className="text-right font-medium">{v}</dd></div>
          ))}
        </dl>
      </div>

      {finalized ? (
        <div className="animate-in-fade mt-4 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <CircleCheck size={20} className="mt-0.5 shrink-0 text-emerald-600" />
          <div className="leading-snug">
            <p className="text-sm font-semibold text-emerald-900">Trip finalized</p>
            <p className="text-[13px] text-emerald-800">{accepted} of {participants.length} accepted. Payments are open.</p>
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <div className="mb-2 flex items-baseline justify-between"><p className="text-[13px] font-medium text-muted">Accepted</p><span className="text-xs text-muted">{accepted} of {need} needed</span></div>
          <Progress value={Math.min(100, (accepted / need) * 100)} />
        </div>
      )}

      <ul className="mt-2 divide-y divide-line">
        {participants.map((id) => (
          <li key={id} className="flex items-center gap-3 py-2.5">
            <Avatar id={id} size={32} />
            <span className="flex-1 text-sm font-medium">{displayName(id)}</span>
            {trip.accepts.includes(id) ? <Badge variant="success">Accepted</Badge> : <span className="text-[13px] text-muted">Waiting</span>}
          </li>
        ))}
      </ul>

      <div className="mt-5 space-y-2">
        {finalized && <Button className="w-full" onClick={() => setStage("settle")}>Go to payments</Button>}
        {going && (
          <Button
            variant={finalized ? "outline" : mine ? "outline" : "default"}
            className="w-full"
            onClick={() => update((t) => ({ accepts: t.accepts.includes("me") ? t.accepts.filter((x) => x !== "me") : [...t.accepts, "me"] }))}
          >
            {mine ? "Withdraw my acceptance" : "Accept plan"}
          </Button>
        )}
        {!going && <p className="text-center text-xs text-muted">You&apos;re not part of this plan, so you can&apos;t accept it.</p>}
        <Button variant="ghost" className="w-full" onClick={() => setStage("picked")}>Back to final cost</Button>
      </div>
    </div>
  );
}
