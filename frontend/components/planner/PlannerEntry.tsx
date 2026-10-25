"use client";
import { useState } from "react";
import { Plus, X } from "lucide-react";
import { usePlanner } from "@/lib/planner-context";
import { useTrip } from "@/lib/trip-context";
import type { PlannerTopic } from "@/lib/types";
import { Button } from "@/components/ui/primitives";
export function PlannerEntry() {
  const state = usePlanner();
  const {setPanelOpen} = useTrip();
  const [menu, setMenu] = useState(false);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState<PlannerTopic>("Dining");
  const [location,setLocation] = useState("");
  if (!state) return null;
  return <><div className="relative"><button type="button" aria-label="Add to chat" aria-expanded={menu} onClick={() => setMenu(!menu)} className="flex size-9 items-center justify-center rounded-full hover:bg-surface"><Plus size={22}/></button>
    {menu && <div className="absolute bottom-12 left-0 z-30 w-44 rounded-xl border border-line bg-white p-2 shadow-lg"><button className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-surface" onClick={() => {setMenu(false); if (state.planner && state.planner.status !== "picked") setPanelOpen(true); else state.setCreating(true);}}>Planner</button></div>}</div>
    {state.creating && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/30 p-4"><form role="dialog" aria-modal="true" aria-label="Start a planner" onSubmit={async e => { e.preventDefault(); if(await state.create(title,topic,location)) {state.setCreating(false);setPanelOpen(true);} }} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-xl">
      <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Start a planner</h2><button type="button" aria-label="Close planner" onClick={() => state.setCreating(false)}><X size={20}/></button></div>
      <p className="text-sm text-muted">Give the plan a name. The conversation will fill in the details together.</p>
      <label className="block text-sm">Title<input autoFocus required maxLength={120} value={title} onChange={e=>setTitle(e.target.value)} className="mt-1 w-full rounded-lg border border-line p-2" placeholder="Friday dinner"/></label>
      <label className="block text-sm">Topic<select value={topic} onChange={e=>setTopic(e.target.value as PlannerTopic)} className="mt-1 w-full rounded-lg border border-line p-2">{["Dining","Travel","Entertainment"].map(t=><option key={t}>{t}</option>)}</select></label>
      <label className="block text-sm">City or area (optional)<input maxLength={200} value={location} onChange={e=>setLocation(e.target.value)} className="mt-1 w-full rounded-lg border border-line p-2" placeholder="Austin"/></label>
      {state.error && <p role="alert" className="text-sm text-red-700">{state.error}</p>}<Button disabled={state.busy}>Start planner</Button>
    </form></div>}
  </>;
}
export function PublicPerspective() {
  const state=usePlanner();
  if(!state?.demoMode) return null;
  return <div className="flex flex-wrap items-center gap-1 border-b border-line bg-amber-50 px-4 py-2 text-xs"><span className="mr-1 text-amber-900">Speak as</span>{Object.values(state.members).map(member=><button key={member.id} aria-pressed={state.speaker===member.id} onClick={()=>state.setSpeaker(member.id)} className={`rounded-full px-2 py-1 ${state.speaker===member.id?"bg-amber-900 text-white":"hover:bg-amber-100"}`}>{member.name}</button>)}<span className="w-full text-[10px] text-amber-900">Public conversation only · private check-in stays yours</span></div>;
}
