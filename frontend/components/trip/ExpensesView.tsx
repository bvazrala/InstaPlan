"use client";

import { useState } from "react";
import { Check, Plus } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import { money } from "@/lib/format";
import { perPerson } from "@/lib/sort";
import { displayName } from "@/lib/trip-model";
import { OPTIONS } from "@/mocks/demo-data";
import { Avatar } from "@/components/chat/Avatar";
import { Badge, Button, Chip, inputCls, Progress } from "@/components/ui/primitives";

/** Step 5: everyone logs what they paid and who it was for. The final cost unlocks when all participants are done. */
export default function ExpensesView() {
  const { trip, participants, pickedId, update, setStage } = useTrip();
  const { expenses, expensesDone } = trip;
  const picked = OPTIONS.find((o) => o.id === pickedId);
  const going = participants.includes("me");
  const meDone = expensesDone.includes("me");
  const done = participants.filter((id) => expensesDone.includes(id)).length;
  const allDone = participants.length > 0 && done === participants.length;

  const [adding, setAdding] = useState(false);
  const [what, setWhat] = useState("");
  const [amount, setAmount] = useState("");
  const [payer, setPayer] = useState("me");
  const [left, setLeft] = useState<string[]>([]); // people unticked from the split

  // The payer can't split with themselves, so only the others are listed. Their own share is still part of the total.
  const others = participants.filter((id) => id !== payer);
  const selected = others.filter((id) => !left.includes(id));
  const n = Number(amount);
  const valid = what.trim() !== "" && n > 0 && selected.length > 0;
  const each = valid ? n / (selected.length + 1) : 0;

  const open = (preset?: { what: string; amount: string }) => { setWhat(preset?.what ?? ""); setAmount(preset?.amount ?? ""); setPayer("me"); setLeft([]); setAdding(true); };
  const add = () => {
    if (!valid) return;
    update((t) => ({ expenses: [...t.expenses, { id: `e${t.expenses.length + 1}`, what: what.trim(), payer, amount: n, split: [payer, ...selected] }] }));
    setAdding(false);
  };
  const lodging = picked ? { what: `${picked.lodging} (${picked.title})`, amount: String(picked.lodgingShare * participants.length) } : null;

  return (
    <div>
      <h3 className="text-lg font-semibold tracking-tight">Expenses</h3>
      <p className="mt-0.5 text-[13px] leading-snug text-muted">Add what you paid for the trip and who it was for. The final cost per person is worked out once everyone has finished.</p>
      {picked && <p className="mt-2 text-xs text-muted">Estimate from your pick: about {money(perPerson(picked))} per person.</p>}

      <h4 className="mb-1 mt-6 text-[13px] font-medium text-muted">Logged</h4>
      {expenses.length === 0 && !adding && <p className="py-2 text-sm text-muted">Nothing logged yet.</p>}
      <ul className="divide-y divide-line">
        {expenses.map((e) => (
          <li key={e.id} className="flex items-center gap-3 py-2.5">
            <Avatar id={e.payer} size={32} />
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-medium">{e.what}</span>
              <span className="block text-xs text-muted">Paid by {displayName(e.payer)} · split with {e.split.length - 1} {e.split.length === 2 ? "other" : "others"}</span>
            </span>
            <span className="text-sm font-semibold">{money(e.amount)}</span>
          </li>
        ))}
      </ul>

      {going && !meDone && (adding ? (
        <div className="animate-in-fade mt-3 space-y-3 rounded-xl border border-line p-3.5 shadow-xs">
          <input autoFocus value={what} onChange={(e) => setWhat(e.target.value)} placeholder="What was it for?" className={inputCls} />
          <div className="flex gap-2">
            <div className="flex h-9 w-1/2 items-center rounded-md border border-line bg-white px-3 shadow-xs focus-within:border-neutral-400 focus-within:ring-[3px] focus-within:ring-neutral-200">
              <span className="text-sm text-muted">$</span>
              <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" placeholder="0" className="w-full bg-transparent px-1 text-sm outline-none" aria-label="Amount" />
            </div>
            <select value={payer} onChange={(e) => setPayer(e.target.value)} className={`${inputCls} w-1/2`} aria-label="Paid by">
              {participants.map((id) => <option key={id} value={id}>{id === "me" ? "Paid by you" : `Paid by ${displayName(id)}`}</option>)}
            </select>
          </div>
          <div>
            <p className="mb-1.5 text-xs text-muted">Split with</p>
            <div className="flex flex-wrap gap-1.5">
              {others.map((id) => (
                <Chip key={id} on={selected.includes(id)} onClick={() => setLeft((l) => (l.includes(id) ? l.filter((x) => x !== id) : [...l, id]))}>{displayName(id)}</Chip>
              ))}
            </div>
            {valid && <p className="mt-2 text-xs text-muted">{payer === "me" ? "You cover your own share" : `${displayName(payer)} covers their own share`}. Each person pays {money(each)}.</p>}
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={() => setAdding(false)}>Cancel</Button>
            <Button className="flex-1" disabled={!valid} onClick={add}>Add expense</Button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-x-2">
          <Button size="sm" variant="outline" onClick={() => open()}><Plus size={14} /> Add expense</Button>
          {lodging && !expenses.some((e) => e.what === lodging.what) && (
            <Button size="sm" variant="ghost" onClick={() => open(lodging)}>Add lodging from your pick</Button>
          )}
        </div>
      ))}

      <h4 className="mb-2 mt-7 flex items-baseline justify-between text-[13px] font-medium text-muted">Finished adding <span className="text-xs font-normal">{done} of {participants.length}</span></h4>
      <Progress value={participants.length ? (done / participants.length) * 100 : 0} />
      <ul className="mt-1 divide-y divide-line">
        {participants.map((id) => (
          <li key={id} className="flex items-center gap-3 py-2">
            <Avatar id={id} size={24} />
            <span className="flex-1 text-[13px] font-medium">{displayName(id)}</span>
            {expensesDone.includes(id) ? <Badge variant="success"><Check size={12} /> Done</Badge> : <span className="text-xs text-muted">Still adding</span>}
          </li>
        ))}
      </ul>

      <div className="mt-5 space-y-2">
        {going && (meDone ? (
          <Button variant="outline" className="w-full" onClick={() => update((t) => ({ expensesDone: t.expensesDone.filter((x) => x !== "me") }))}>Reopen my expenses</Button>
        ) : (
          <Button className="w-full" onClick={() => { setAdding(false); update((t) => ({ expensesDone: [...t.expensesDone, "me"] })); }}>I&apos;m done adding expenses</Button>
        ))}
        {allDone && <Button className="w-full" onClick={() => setStage("picked")}>See final cost</Button>}
        {!allDone && meDone && <p className="text-center text-xs text-muted">Waiting for {participants.length - done} {participants.length - done === 1 ? "person" : "people"} to finish.</p>}
      </div>
    </div>
  );
}
