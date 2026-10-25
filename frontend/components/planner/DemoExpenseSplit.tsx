"use client";
import { useState } from "react";
import { Check, CreditCard, RotateCcw, Wallet } from "lucide-react";
import { usePlanner } from "@/lib/planner-context";
import { Avatar } from "@/components/chat/Avatar";

const methods = ["Demo card", "Demo Venmo", "Demo Apple Pay"] as const;
type Method = typeof methods[number];

export function expenseCents(value: string): number | null {
  if (!/^\d{1,6}(?:\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return cents > 0 ? cents : null;
}
export function equalShares(total: number, ids: string[]) {
  const members = [...new Set(ids)].sort();
  return Object.fromEntries(members.map((id, index) => [id, Math.floor(total / members.length) + (index < total % members.length ? 1 : 0)]));
}
const money = (cents: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);

export default function DemoExpenseSplit({ place }: { place: string }) {
  const state = usePlanner()!;
  const [amount, setAmount] = useState("120.00");
  const [method, setMethod] = useState<Method>("Demo card");
  const [payments, setPayments] = useState<Record<string, Method>>({});
  const [notice, setNotice] = useState("");
  const ids = [...new Set(state.planner!.pricedMembers)].sort();
  const total = expenseCents(amount);
  const shares = total === null ? {} : equalShares(total, ids);
  const paid = ids.reduce((sum, id) => sum + (payments[id] ? shares[id] ?? 0 : 0), 0);
  const actor = state.speaker;
  const mine = shares[actor];
  const locked = Object.keys(payments).length > 0;
  if (!state.demoMode || !ids.length) return null;
  const pay = () => {
    if (!total || mine === undefined || mine === 0 || payments[actor]) return;
    setPayments(current => ({ ...current, [actor]: method }));
    setNotice(`${state.members[actor]?.name ?? "Member"} prepaid ${money(mine)} with ${method}. Simulation only.`);
  };
  return <section aria-label="Demo expense split" className="animate-in-fade overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-sm">
    <div className="flex items-start justify-between gap-3 border-b border-emerald-100 bg-emerald-50/70 p-4">
      <div><h3 className="flex items-center gap-2 text-sm font-semibold"><Wallet size={16} className="text-emerald-700"/>Split the plan</h3><p className="mt-1 text-xs text-muted">{place}</p></div>
      <span className="shrink-0 rounded-full border border-emerald-200 bg-white px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-emerald-800">Demo</span>
    </div>
    <div className="space-y-4 p-4">
      <p className="text-[11px] leading-relaxed text-muted">Try a shared advance payment. This sample amount is editable, not a venue quote. No real money moves.</p>
      <label className="block text-xs font-medium">Shared expense (USD)<div className="mt-1.5 flex items-center rounded-xl border border-line bg-surface px-3"><span className="text-sm text-muted">$</span><input aria-label="Shared expense (USD)" inputMode="decimal" value={amount} disabled={locked} onChange={event => { setAmount(event.target.value); setNotice(""); }} className="min-w-0 flex-1 bg-transparent p-2.5 text-lg font-semibold outline-none disabled:text-muted"/></div></label>
      {total === null && <p role="alert" className="text-xs text-red-700">Enter an amount from $0.01 to $999,999.99, with up to two decimals.</p>}
      <div className="flex items-center justify-between text-xs"><span className="text-muted">Split equally · {ids.length} going</span><span className="font-semibold text-emerald-700">{money(paid)} prepaid</span></div>
      <div role="progressbar" aria-label="Advance payments collected" aria-valuemin={0} aria-valuemax={total ?? 0} aria-valuenow={paid} className="h-1.5 overflow-hidden rounded-full bg-emerald-50"><div style={{ width: `${total ? paid / total * 100 : 0}%` }} className="h-full rounded-full bg-emerald-500 transition-all duration-500"/></div>
      <ul className="space-y-3" aria-label="Expense shares">{ids.map(id => <li key={id} className="flex items-center gap-2.5"><Avatar id={id} members={state.members} size={30}/><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium">{state.members[id]?.name ?? "Member"}{id === actor ? " (you)" : ""}</p><p className={`mt-0.5 text-[10px] ${payments[id] ? "text-emerald-700" : "text-muted"}`}>{payments[id] ? `Prepaid · ${payments[id]}` : "Awaiting advance payment"}</p></div><span className="flex items-center gap-1 text-xs font-semibold">{payments[id] && <Check size={13} className="text-emerald-600"/>}{shares[id] === undefined ? "—" : money(shares[id])}</span></li>)}</ul>
      <div className="border-t border-line pt-3">
        {mine !== undefined ? <><label className="block text-[11px] font-medium">Mock payment method<select aria-label="Mock payment method" value={method} onChange={event => setMethod(event.target.value as Method)} disabled={!!payments[actor]} className="mt-1.5 w-full rounded-xl border border-line bg-white p-2.5 text-xs">{methods.map(item => <option key={item}>{item}</option>)}</select></label><button onClick={pay} disabled={total === null || !!payments[actor] || mine === 0} className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-3 py-3 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:bg-emerald-100 disabled:text-emerald-800">{payments[actor] ? <><Check size={15}/>Your share is prepaid</> : <><CreditCard size={15}/>Simulate prepaying {money(mine)}</>}</button></> : <p className="text-xs text-muted">Only going members are included. Switch to a going demo speaker to try paying.</p>}
        <p role="status" className="mt-2 text-[11px] leading-relaxed text-emerald-800">{notice || (total && paid === total ? "Everyone is prepaid. Your demo split is settled." : `Remaining: ${total === null ? "—" : money(total - paid)}`)}</p>
      </div>
      {locked && <button className="flex items-center gap-1 text-[11px] font-medium text-muted" onClick={() => { setPayments({}); setNotice(""); }}><RotateCcw size={12}/>Reset mock payments</button>}
      <p className="text-[10px] leading-relaxed text-muted">Demo only · local to this card · no booking or payment is made. Use the speaker switcher to simulate each member.</p>
    </div>
  </section>;
}
