"use client";
import { Check, X } from "lucide-react";
import { Avatar } from "@/components/chat/Avatar";
import { usePlanner } from "@/lib/planner-context";
export default function PollPeople(){
  const state=usePlanner()!;const p=state.planner!;
  const ids=Object.keys(p.attendance??{}).sort((a,b)=>Number(p.poll.approvals.includes(b))-Number(p.poll.approvals.includes(a)));
  const visible=ids.slice(0,4),extra=ids.slice(4);
  const declined=ids.filter(id=>p.attendance[id].status==='not_going');
  return <div className="space-y-2"><div className="flex items-center -space-x-1" aria-label="Plan responses">{visible.map(id=>{
    const no=declined.includes(id),yes=p.poll.approvals.includes(id),going=p.attendance[id].status==='going';
    const label=`${state.members[id]?.name??'Member'}: ${no?'not coming':yes?'confirmed':going?'going, awaiting vote':'awaiting response'}`;
    return <span key={id} title={label} aria-label={label} className={`relative rounded-full border-2 bg-white p-0.5 ${no?'border-rose-200':yes?'border-emerald-200':'border-white'}`}><Avatar id={id} size={34} members={state.members}/>{(no||yes)&&<span className={`absolute -bottom-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full border-2 border-white text-white ${no?'bg-rose-500':'bg-emerald-500'}`}>{no?<X size={10} strokeWidth={3}/>:<Check size={10} strokeWidth={3}/>}</span>}</span>;
  })}{!!extra.length&&<span title={extra.map(id=>state.members[id]?.name??'Member').join(', ')} aria-label={`${extra.length} more people`} className="relative flex size-10 items-center justify-center rounded-full border-2 border-white bg-surface text-xs font-semibold text-muted">+{extra.length}</span>}</div>
  <p className="text-[11px] text-muted">{p.poll.approvals.length} confirmed{declined.length?` · ${declined.length} not coming`:''} · {p.poll.required} needed · {ids.length-p.poll.approvals.length-declined.length} awaiting vote</p></div>;
}
