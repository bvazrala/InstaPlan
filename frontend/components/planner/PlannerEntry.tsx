"use client";
import { useState } from "react";
import { Plus, X, Utensils, Plane, Ticket, RotateCcw } from "lucide-react";
import { usePlanner } from "@/lib/planner-context";
import { useTrip } from "@/lib/trip-context";
import type { PlannerTopic } from "@/lib/types";
import { Button } from "@/components/ui/primitives";
import { Avatar } from "@/components/chat/Avatar";
import CreationLocation, {type ChosenPlace} from "./CreationLocation";
function CreationDialog(){
  const state=usePlanner()!;const {setPanelOpen}=useTrip();
  const [title,setTitle]=useState("");const [topic,setTopic]=useState<PlannerTopic>("Dining");
  const [location,setLocation]=useState("");const [place,setPlace]=useState<ChosenPlace|null>(null);
  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/30 p-4"><form role="dialog" aria-modal="true" aria-label="Start a planner" onSubmit={async e=>{e.preventDefault();if(await state.create(title,topic,location,place??undefined)){state.setCreating(false);setPanelOpen(false);}}} onKeyDown={e=>{if(e.key==='Escape')state.setCreating(false);}} className="max-h-[90dvh] w-full max-w-md space-y-5 overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
    <div className="flex items-center justify-between"><h2 className="text-xl font-semibold tracking-tight">Plan something together</h2><button type="button" aria-label="Close planner" onClick={()=>state.setCreating(false)}><X size={20}/></button></div>
    <p className="text-sm text-muted">Start with an idea. The conversation fills in the rest.</p>
    <label className="block text-xs font-medium">Title<input autoFocus required maxLength={120} value={title} onChange={e=>setTitle(e.target.value)} className="mt-2 w-full rounded-xl border border-line p-3 text-sm outline-none focus:border-violet-400" placeholder="Saturday with the crew"/></label>
    <CreationLocation chatId={state.chatId} value={location} chosen={place} onChange={value=>{setLocation(value);setPlace(null);}} onChoose={(label,selection)=>{setLocation(label);setPlace(selection);}}/>
    <fieldset><legend className="mb-2 text-xs font-medium">Type</legend><div className="grid grid-cols-3 gap-2">{([['Dining',Utensils],['Travel',Plane],['Entertainment',Ticket]] as const).map(([value,Icon])=><label key={value} className={`flex cursor-pointer flex-col items-center gap-2 rounded-2xl border px-2 py-3 text-[11px] font-medium ${topic===value?'border-violet-400 bg-violet-50 text-violet-800':'border-line text-muted hover:bg-surface'}`}><input className="sr-only" type="radio" name="topic" value={value} checked={topic===value} onChange={()=>setTopic(value)}/><Icon size={20}/>{value}</label>)}</div></fieldset>
    {state.error&&<p role="alert" className="text-xs text-red-700">{state.error}</p>}
    <Button className="w-full rounded-xl" disabled={state.busy||!title.trim()}>Start planner</Button>
  </form></div>;
}
export function PlannerEntry(){
  const state=usePlanner();const {setPanelOpen}=useTrip();const [menu,setMenu]=useState(false);
  if(!state)return null;
  return <><div className="relative"><button type="button" aria-label="Add to chat" aria-haspopup="menu" aria-expanded={menu} onClick={()=>setMenu(!menu)} className="flex size-9 items-center justify-center rounded-full bg-violet-50 text-violet-700 hover:bg-violet-100"><Plus size={22}/></button>{menu&&<div role="menu" className="absolute bottom-12 left-0 z-30 w-44 rounded-xl border border-line bg-white p-2 shadow-lg"><button role="menuitem" className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-surface" onClick={()=>{setMenu(false);if(state.planner&&state.planner.status!=='picked')setPanelOpen(true);else state.setCreating(true);}}>Planner</button></div>}</div>{state.creating&&<CreationDialog/>}</>;
}
export function PublicPerspective(){
  const state=usePlanner();if(!state?.demoMode)return null;
  return <div className="flex flex-wrap items-center gap-1 border-b border-line bg-amber-50 px-3 py-2 text-xs"><span className="mr-1 text-amber-900">Speak as</span>{Object.values(state.members).map(member=><button key={member.id} aria-label={member.name} aria-pressed={state.speaker===member.id} onClick={()=>state.setSpeaker(member.id)} className={`flex items-center gap-1.5 rounded-full py-1 pl-1 pr-2 ${state.speaker===member.id?'bg-white shadow-sm ring-1 ring-amber-300':'hover:bg-amber-100'}`}><Avatar id={member.id} size={23} members={state.members}/>{member.name}</button>)}<button title="Clear the demo conversation and start a new plan" disabled={state.busy} onClick={()=>void state.reset()} className="ml-auto flex items-center gap-1 rounded-full px-2 py-1.5 text-[11px] font-medium text-amber-900 hover:bg-amber-100"><RotateCcw size={13}/>Reset demo</button></div>;
}
