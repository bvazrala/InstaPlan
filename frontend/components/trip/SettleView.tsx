"use client";

import { Check, Lock } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import { money } from "@/lib/format";
import { transfersFor } from "@/lib/expenses";
import { displayName } from "@/lib/trip-model";
import { Avatar } from "@/components/chat/Avatar";
import { Button, Progress } from "@/components/ui/primitives";

/** Step 8: who pays whom, worked out from the logged expenses. Opens once the trip is finalized. */
export default function SettleView() {
  const { trip, participants, update, setStage, need, accepted, finalized } = useTrip();
  const { expenses, paid } = trip;

  if (!finalized) {
    return (
      <div className="flex flex-col items-center pt-6 text-center">
        <span className="flex size-14 items-center justify-center rounded-full border border-line"><Lock size={22} strokeWidth={1.5} /></span>
        <h3 className="mt-4 text-lg font-semibold tracking-tight">Payments aren&apos;t open yet</h3>
        <p className="mt-1 max-w-[270px] text-sm text-muted">They open once more than half of the people going have accepted the final plan.</p>
        <div className="mt-5 w-full"><Progress value={Math.min(100, (accepted / need) * 100)} /><p className="mt-2 text-xs text-muted">{accepted} of {need} needed have accepted</p></div>
        <Button className="mt-5 w-full" onClick={() => setStage("finalize")}>Go to finalize</Button>
      </div>
    );
  }

  const transfers = transfersFor(expenses, participants);
  return (
    <div>
      <h3 className="text-lg font-semibold tracking-tight">Payments</h3>
      <p className="mt-0.5 text-[13px] leading-snug text-muted">Worked out from the {expenses.length} {expenses.length === 1 ? "expense" : "expenses"} the group logged.</p>

      <h4 className="mb-1 mt-6 text-[13px] font-medium text-muted">Who pays whom</h4>
      {transfers.length === 0 ? (
        <p className="py-2 text-sm text-muted">{expenses.length ? "Everyone is settled." : "No expenses were logged, so nobody owes anything."}</p>
      ) : (
        <ul className="divide-y divide-line">
          {transfers.map((t) => {
            const key = `${t.from}>${t.to}:${t.amount}`;
            const done = paid.includes(key);
            const mine = t.from === "me";
            return (
              <li key={key} className="flex items-center gap-3 py-2.5">
                <Avatar id={t.from} size={32} />
                <span className="min-w-0 flex-1 text-sm leading-tight">
                  <span className="font-medium">{displayName(t.from)}</span> <span className="text-muted">to</span> <span className="font-medium">{displayName(t.to)}</span>
                </span>
                <span className="text-sm font-semibold">{money(t.amount)}</span>
                {mine ? (
                  <Button size="sm" variant={done ? "secondary" : "default"} disabled={done} className="min-w-16" onClick={() => update((s) => ({ paid: [...s.paid, key] }))}>
                    {done ? <Check size={15} /> : "Pay"}
                  </Button>
                ) : (
                  <span className="min-w-16 text-center text-[13px] text-muted">{done ? "Paid" : "Owes"}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <p className="mt-3 text-xs text-muted">Payments go through Capital One Nessie (sandbox).</p>
    </div>
  );
}
