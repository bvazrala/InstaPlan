"use client";
import { CalendarDays, MapPin, Check, Users, Sparkles, Utensils, Plane, Ticket } from "lucide-react";
import { usePlanner } from "@/lib/planner-context";
export default function PlanSummary({compact=false}:{compact?:boolean}){
  const state=usePlanner();if(!state?.planner)return null;
  const p=state.planner,t=p.template,confirmed=p.status!=="collecting";
  const going=Object.entries(p.attendance??{}).filter(([,entry])=>entry.status==="going").map(([id])=>id);
  const pending=Object.values(p.attendance??{}).filter(entry=>entry.status==="conditional").length;
  const cluster=Object.entries(t.cluster??{}).filter(([,value])=>Array.isArray(value)?value.length:!!value);
  const names=(ids:string[])=>ids.map(id=>state.members[id]?.name??"Member").join(", ");
  const windows=going.map(id=>{const values=t.when.flexibility?.[id];return values===null?`${state.members[id]?.name??"Member"}: flexible`:values?.map(w=>w.label).join(", ");}).filter(Boolean);
  const time=t.when.agreed?.label??(windows.length?windows.join(" · "):"Timing is still taking shape");
  const publicPreferences=[...new Set(Object.entries(t.preferences??{}).filter(([id])=>p.attendance?.[id]?.status!=='not_going').flatMap(([,values])=>values))];
  const publicRequirements=[...new Set(Object.entries(t.hardConstraints??{}).filter(([id])=>p.attendance?.[id]?.status!=='not_going').flatMap(([,values])=>values))];
  const Icon=p.topic==="Dining"?Utensils:p.topic==="Travel"?Plane:Ticket;
  return <section aria-label={confirmed?"Confirmed plan summary":"Plan summary"} className={`rounded-2xl border ${confirmed?"border-emerald-200 bg-emerald-50/60":"border-violet-100 bg-white"} ${compact?"p-4":"p-5"}`}>
    <div className={`${compact?"mb-2":"mb-4"} flex items-center justify-between gap-2`}><span className={`flex items-center gap-1.5 text-[11px] font-semibold ${confirmed?"text-emerald-800":"text-violet-700"}`}>{confirmed?<Check size={14}/>:<Icon size={14}/>} {confirmed?(p.status==="picked"?"Plan selected":"Plan confirmed"):p.topic+" plan"}</span>{confirmed&&compact&&<span className="text-[10px] text-emerald-700">{p.poll.approvals.length} approved</span>}{!confirmed&&p.listening!=="idle"&&<span className="flex items-center gap-1 text-[10px] text-muted"><Sparkles size={11}/>{p.listening==="failed"?"Needs a retry":"Listening…"}</span>}</div>
    {compact?<h3 className="text-lg font-semibold tracking-tight">{p.title}</h3>:<h2 className="text-xl font-semibold tracking-tight">{p.title}</h2>}
    <dl className={`${compact?"mt-3 space-y-2":"mt-4 space-y-3"} text-[13px]`}><div className="flex gap-2.5"><MapPin size={16} className="mt-0.5 shrink-0 text-muted"/><div><dt className="sr-only">Where</dt><dd>{t.where.destination?.name??t.where.searchArea??"Choosing a place together"}</dd></div></div>
      <div className="flex gap-2.5"><CalendarDays size={16} className="mt-0.5 shrink-0 text-muted"/><div><dt className="sr-only">When</dt><dd>{time}{t.when.agreed?.date&&<span className="block text-xs text-muted">{t.when.agreed.date} · {p.timezone}</span>}</dd></div></div>
      <div className="flex gap-2.5"><Users size={16} className="mt-0.5 shrink-0 text-muted"/><div><dt className="sr-only">Who’s going</dt><dd>{going.length?names(going):"No one has confirmed attendance yet"}{pending>0&&<span className="block text-xs text-muted">{pending} yet to respond</span>}</dd></div></div>
    </dl>
    {!!cluster.length&&<div className="mt-4 flex flex-wrap gap-1.5">{cluster.map(([key,value])=><span key={key} className="rounded-full border border-black/5 bg-white/80 px-2.5 py-1 text-[11px] text-neutral-600">{Array.isArray(value)?value.join(", "):value}{t.sources?.[`${key}:group`]==="suggested"&&<span className="ml-1 text-violet-500">· Suggested</span>}</span>)}</div>}
    {!!publicPreferences.length&&<p className="mt-3 text-xs leading-relaxed text-muted">Preferences: {publicPreferences.slice(0,4).join(' · ')}</p>}
    {!!publicRequirements.length&&<p className="mt-2 text-xs leading-relaxed text-neutral-700">Needs: {publicRequirements.slice(0,4).join(' · ')}</p>}
    {confirmed&&!compact&&<p className="mt-4 border-t border-emerald-100 pt-3 text-[11px] text-emerald-800">{p.poll.approvals.length} approved · recommendations for {p.pricedMembers.length} going {p.pricedMembers.length===1?"member":"members"}</p>}
  </section>;
}
