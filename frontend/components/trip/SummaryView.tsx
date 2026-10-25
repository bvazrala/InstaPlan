"use client";

import { Lock } from "lucide-react";
import { OPTIONS } from "@/mocks/demo-data";
import { money } from "@/lib/format";
import { paidBy, shareOf, totalOf } from "@/lib/expenses";
import { displayName } from "@/lib/trip-model";
import { useTrip } from "@/lib/trip-context";
import { Avatar } from "@/components/chat/Avatar";
import { Button, PrimaryButton, Progress } from "@/components/ui/primitives";

/** Step 6: final cost per person, from the expenses everyone logged. Locked until all participants are done. */
export default function SummaryView() {
  const { trip, participants, pickedId, profile, setStage } = useTrip();
  const { expenses, expensesDone } = trip;
  const done = participants.filter((id) => expensesDone.includes(id)).length;

  if (participants.length === 0 || done < participants.length) {
    return (
      <div className="flex flex-col items-center pt-6 text-center">
        <span className="flex size-14 items-center justify-center rounded-full border border-line"><Lock size={22} strokeWidth={1.5} /></span>
        <h3 className="mt-4 text-lg font-semibold tracking-tight">Final cost isn&apos;t ready</h3>
        <p className="mt-1 max-w-[270px] text-sm text-muted">It&apos;s worked out once everyone going has finished adding expenses.</p>
        <div className="mt-5 w-full"><Progress value={participants.length ? (done / participants.length) * 100 : 0} /><p className="mt-2 text-xs text-muted">{done} of {participants.length} finished</p></div>
        <Button className="mt-5 w-full" onClick={() => setStage("expenses")}>Back to expenses</Button>
      </div>
    );
  }

  const o = OPTIONS.find((x) => x.id === pickedId);
  const total = totalOf(expenses);
  const dest = o?.place ?? profile.group.destination?.value ?? "Trip";
  const dates = o?.dates ?? profile.group.dates?.value;

  return (
    <div>
      <div className="rounded-xl bg-neutral-900 p-5 text-white">
        <p className="text-xs font-medium text-white/70">{dates ?? "Dates not set"} · {participants.length} people</p>
        <p className="mt-6 text-2xl font-semibold leading-tight tracking-tight">{dest}</p>
        {o && <p className="text-sm text-white/70">{o.title} · {o.lodging}</p>}
      </div>

      <dl className="mt-4 grid grid-cols-2 divide-x divide-line rounded-xl border border-line py-3 text-center shadow-xs">
        <div><dt className="text-xs text-muted">Group total</dt><dd className="text-xl font-semibold">{money(total)}</dd></div>
        <div><dt className="text-xs text-muted">Average each</dt><dd className="text-xl font-semibold">{money(total / participants.length)}</dd></div>
      </dl>

      <h4 className="mb-1 mt-6 text-[13px] font-medium text-muted">Final cost per person</h4>
      <ul className="divide-y divide-line">
        {participants.map((id) => (
          <li key={id} className="flex items-center gap-3 py-2.5">
            <Avatar id={id} size={32} />
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block text-sm font-medium">{displayName(id)}</span>
              <span className="block text-xs text-muted">Paid {money(paidBy(expenses, id))}</span>
            </span>
            <span className="text-sm font-semibold">{money(shareOf(expenses, id))}</span>
          </li>
        ))}
      </ul>
      {expenses.length === 0 && <p className="mt-2 text-xs text-muted">No expenses were logged.</p>}

      <div className="mt-6 flex gap-2">
        <Button variant="secondary" className="flex-1" onClick={() => setStage("expenses")}>Back</Button>
        <PrimaryButton onClick={() => setStage("finalize")} className="flex-1">Continue to finalize</PrimaryButton>
      </div>
    </div>
  );
}
