"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/primitives";
type PrivatePrefs = {budgetCap:number|null;dietary:string[];accessibility:string[];noGos:string;privateScores:Record<string,number>;originLocation?:unknown};
export default function LivePrivateCheckIn({tripId}:{tripId:string}) {
  const [open,setOpen]=useState(false);
  const [prefs,setPrefs]=useState<PrivatePrefs|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [saved,setSaved]=useState(false);
  return <section className="rounded-xl border border-line p-3"><button className="text-sm font-semibold" aria-expanded={open} onClick={async()=>{setOpen(!open);if(!open&&!prefs){setBusy(true);try{setPrefs(await apiFetch(`/trips/${tripId}/me/private`));}catch{setError("Could not load your private check-in.");}finally{setBusy(false);}}}}>Your private check-in</button>
    {open&&<div className="mt-3 space-y-3"><p className="text-xs text-muted">Only your authenticated account can read these answers. The public speaker switcher never changes this identity. Budgets apply to travel groups of at least three.</p>
      {prefs&&<form className="space-y-3" onSubmit={async e=>{e.preventDefault();setBusy(true);setSaved(false);setError("");try{setPrefs(await apiFetch(`/trips/${tripId}/me/private`,{method:"PUT",body:JSON.stringify(prefs)}));setSaved(true);}catch{setError("Could not save your private check-in.");}finally{setBusy(false);}}}>
        <label className="block text-xs">Your maximum travel subtotal (USD, optional)<input aria-label="Your private budget" type="number" min="0" step="0.01" value={prefs.budgetCap??""} onChange={e=>{setSaved(false);setPrefs({...prefs,budgetCap:e.target.value===""?null:Number(e.target.value)});}} className="mt-1 w-full rounded-lg border border-line p-2 text-sm"/></label>
        <label className="block text-xs">Your dietary requirements<input value={prefs.dietary.join("; ")} onChange={e=>setPrefs({...prefs,dietary:e.target.value.split(";").map(s=>s.trim()).filter(Boolean)})} className="mt-1 w-full rounded-lg border border-line p-2 text-sm"/></label>
        <label className="block text-xs">Your accessibility requirements<input value={prefs.accessibility.join("; ")} onChange={e=>setPrefs({...prefs,accessibility:e.target.value.split(";").map(s=>s.trim()).filter(Boolean)})} className="mt-1 w-full rounded-lg border border-line p-2 text-sm"/></label>
        <label className="block text-xs">Your private no-gos<textarea value={prefs.noGos} onChange={e=>setPrefs({...prefs,noGos:e.target.value})} className="mt-1 w-full rounded-lg border border-line p-2 text-sm"/></label>
        <Button disabled={busy}>Save private requirements</Button>{saved&&<p role="status" className="text-xs">Saved privately. Refresh recommendations to apply your changes.</p>}
      </form>}{busy&&!prefs&&<p role="status" className="text-xs">Loading your check-in…</p>}{error&&<p role="alert" className="text-xs text-red-700">{error}</p>}
    </div>}
  </section>;
}
