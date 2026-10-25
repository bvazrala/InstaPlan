"use client";
import { usePlanner } from "@/lib/planner-context";
import { useTrip } from "@/lib/trip-context";
import PlanSummary from "./PlanSummary";
import { PlannerApprovalCard } from "./PlannerPanel";
import ChatPlanWidget from "./widgets/ChatPlanWidget";
export default function PlannerChatCard(){
  const state=usePlanner();const {setPanelOpen}=useTrip();
  if(!state?.planner)return null;
  const p=state.planner;
  if(p.status==='collecting'&&!p.poll.ready)return <div className="my-4 flex max-w-[338px] items-center gap-3 rounded-2xl border border-violet-100 bg-violet-50/50 px-4 py-3" aria-label="Planner listening"><span className="size-2 shrink-0 animate-pulse rounded-full bg-violet-400"/><div className="min-w-0 flex-1"><h3 className="truncate text-sm font-semibold">{p.title}</h3><p className="mt-0.5 text-[11px] text-muted">{p.listening==='failed'?'Listening needs a retry':'Listening to the conversation'}</p></div><button className="text-xs font-semibold text-violet-700" onClick={()=>setPanelOpen(true)}>Details</button></div>;
  return <div className="animate-in-fade my-5 w-full max-w-[362px]" aria-label="Chat plan">
    <div className={p.status==='collecting'?'overflow-hidden rounded-2xl border border-violet-100 [&>section]:mt-0 [&>section]:rounded-none [&>section]:border-0':''}><PlanSummary compact/>{p.status==='collecting'&&<PlannerApprovalCard/>}</div>
    {state.error&&<p role="alert" className="mt-2 text-xs text-red-700">{state.error}</p>}
    {p.status!=="collecting"&&<ChatPlanWidget onOpen={()=>setPanelOpen(true)}/>}
    {p.status==="approved"&&p.generation.status==="needs_input"&&<button onClick={()=>setPanelOpen(true)} className="mt-3 block rounded-xl border border-violet-100 bg-violet-50 px-4 py-3 text-left text-xs font-medium text-violet-800">Your plan is approved. Finish the search details →</button>}
  </div>;
}
