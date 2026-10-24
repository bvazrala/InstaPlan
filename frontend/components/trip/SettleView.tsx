"use client";

import { useState } from "react";
import { Check, Plus } from "lucide-react";
import { money } from "@/lib/format";
import { Avatar } from "@/components/chat/Avatar";
import { Card, GhostButton, Label } from "@/components/ui/primitives";

const EXPENSES = [{ id: "e1", what: "Rental deposit (LES loft)", payer: "maya", amount: 860 }];
const SPLIT = [
  { from: "me", to: "maya", amount: 215 },
  { from: "alex", to: "maya", amount: 215 },
  { from: "sam", to: "maya", amount: 215 },
];

export default function SettleView() {
  const [paid, setPaid] = useState<string[]>([]);
  return (
    <div className="space-y-3">
      <div>
        <Label>Shared expenses</Label>
        {EXPENSES.map((e) => (
          <Card key={e.id} className="flex items-center gap-3">
            <Avatar id={e.payer} size={30} />
            <div className="flex-1"><p className="text-[13px] font-semibold">{e.what}</p><p className="text-[11px] text-muted">Paid by Maya · split 4 ways</p></div>
            <p className="font-bold">{money(e.amount)}</p>
          </Card>
        ))}
        <GhostButton className="mt-2 flex items-center justify-center gap-1.5"><Plus size={14} /> Log an expense</GhostButton>
      </div>

      <div>
        <Label>Suggested transfers</Label>
        <ul className="space-y-2">
          {SPLIT.map((t) => {
            const key = t.from;
            const done = paid.includes(key);
            return (
              <li key={key} className="flex items-center gap-3 rounded-2xl bg-surface px-3 py-2.5">
                <Avatar id={t.from} size={26} />
                <span className="flex-1 text-[13px]"><b>{t.from === "me" ? "You" : t.from[0].toUpperCase() + t.from.slice(1)}</b> → Maya</span>
                <span className="text-[13px] font-bold">{money(t.amount)}</span>
                <button onClick={() => setPaid((p) => [...p, key])} disabled={done}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${done ? "bg-emerald-100 text-emerald-700" : "brand-gradient text-white"}`}>
                  {done ? <Check size={13} /> : "Pay"}
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-[11px] text-muted">Transfers run through Capital One Nessie (sandbox accounts).</p>
      </div>
    </div>
  );
}
