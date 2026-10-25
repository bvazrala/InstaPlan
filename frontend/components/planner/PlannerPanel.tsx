"use client";
import { useState } from "react";
import { Pencil, MessageCircle, ChevronLeft } from "lucide-react";
import { usePlanner } from "@/lib/planner-context";
import { Button } from "@/components/ui/primitives";
import PollPeople from "./PollPeople";
import ChatPlanWidget from "./widgets/ChatPlanWidget";
import PlanSummary from "./PlanSummary";
import PlannerEditor from "./PlannerEditor";
import { PricingForm } from "./PlannerRecommendations";
export function PlannerApprovalCard(){
  const state=usePlanner();if(!state?.planner)return null;
  const p=state.planner;if(p.status!=="collecting"||!p.poll.ready)return null;
  const yes=p.poll.approvals.includes(state.speaker);
  const no=p.attendance?.[state.speaker]?.status==='not_going';
  return <section aria-label="Join this plan" className="mt-3 rounded-2xl border border-violet-100 bg-violet-50/60 p-4">
    <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold">Who’s coming?</h3><span className="flex items-center gap-1.5 text-[10px] font-semibold text-red-600"><span className="live-voting-dot size-1.5 rounded-full bg-red-500"/>Live vote</span></div><PollPeople/>
    <div className="mt-4 flex gap-2"><button className={`flex-1 rounded-xl px-3 py-2.5 text-xs font-semibold text-white ${yes?'bg-emerald-700':'bg-emerald-600 hover:bg-emerald-700'}`} disabled={state.busy} onClick={()=>void state.respond(true)}>{yes?'✓ You’re going':"Yes, I’m going"}</button><button className={`rounded-xl border px-3 py-2.5 text-xs font-medium ${no?'border-rose-300 bg-rose-50 text-rose-700':'border-line bg-white text-muted'}`} disabled={state.busy} onClick={()=>void state.respond(false)}>{no?'Not coming ✓':'Not coming'}</button></div>
  </section>;

}
export default function PlannerPanel(){
  const state=usePlanner()!;
  const [editing,setEditing]=useState(false);
  if(state.loading)return <p role="status" className="p-5 text-sm">Loading planner…</p>;
  if(!state.planner)return <div className="space-y-4 p-6"><span className="inline-flex size-10 items-center justify-center rounded-2xl bg-violet-50 text-violet-600"><MessageCircle size={20}/></span><h2 className="text-xl font-semibold">A plan starts with a conversation</h2><p className="text-sm leading-relaxed text-muted">Name the idea, choose a topic, and keep chatting. Your plan will take shape here.</p>{state.error&&<p role="alert" className="text-sm text-red-700">{state.error}</p>}<Button onClick={()=>state.setCreating(true)}>Start planner</Button></div>;
  const p=state.planner,frozen=p.status!=="collecting";
  if(editing&&!frozen)return <div><div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-white px-5 py-3"><button onClick={()=>setEditing(false)} className="flex items-center gap-1 text-xs font-semibold"><ChevronLeft size={14}/>Back to plan</button><Button variant="outline" onClick={()=>setEditing(false)}>Done</Button></div><PlannerEditor/></div>;
  return <div className="space-y-5 p-5" aria-label="Live planner template">
    <PlanSummary/>
    {state.error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700">{state.error}</p>}
    {!frozen&&<><div className="rounded-xl bg-surface/70 p-4"><p className="flex items-center gap-2 text-sm font-medium"><MessageCircle size={16}/>Keep the conversation going</p><p role="status" className="mt-1 text-xs leading-relaxed text-muted">{p.poll.ready?"The essentials are here. Review the summary and approve it in the chat.":p.listening==="failed"?"Listening needs a retry. You can also correct the details yourself.":"Share when you’re free and what you have in mind. I’ll bring it together."}</p></div>
      <button onClick={()=>setEditing(true)} className="flex items-center gap-2 text-xs font-semibold text-violet-700"><Pencil size={14}/>Edit details</button>
      {p.listening==="failed"&&<Button variant="outline" disabled={state.busy} onClick={()=>void state.action("retry")}>Retry listening</Button>}
      <details className="rounded-xl border border-line p-3"><summary className="cursor-pointer text-xs text-muted">{p.missing.length?"What’s still needed":"Approval settings"}</summary><div className="mt-3 space-y-3 text-xs text-muted">{p.missing.map((item,i)=><p key={i}>{item.startsWith("where.")?"A city or destination":item.startsWith("when.")?"Availability from going members, or agreed timing":item}</p>)}<label>Group approval <select aria-label="Approval threshold" value={p.poll.threshold} onChange={e=>void state.edit("threshold",Number(e.target.value))} className="ml-2 rounded-lg border border-line p-1">{[.4,.5,.6].map(n=><option key={n} value={n}>{Math.round(n*100)}%</option>)}</select></label></div></details>
    </>}
    {frozen&&<><ChatPlanWidget onOpen={()=>setEditing(false)} embedded/>
      {p.topic==='Travel'&&<details className="rounded-xl border border-line p-3"><summary className="cursor-pointer text-xs font-medium text-muted">Optional flight details</summary><div className="mt-3"><PricingForm key={p.generation.runId}/></div></details>}
      <button className="text-xs font-medium text-muted" disabled={state.busy} onClick={()=>void state.action("revise")}>Revise plan</button></>}

  </div>;
}
