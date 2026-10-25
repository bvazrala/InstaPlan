"use client";
import { useState } from "react";
import { usePlanner } from "@/lib/planner-context";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/primitives";

const input = "w-full rounded-lg border border-line bg-white p-2 text-sm";
function Editable({label,value,onSave,disabled=false,source}:{label:string;value:string;onSave:(value:string)=>Promise<boolean>;disabled?:boolean;source?:string}) {
  const [draft,setDraft]=useState(value);
  const planner = usePlanner();
  const author = source ? planner?.members[planner.planner?.provenance[source] ?? ""]?.name : undefined;
  return <form className="space-y-1" onSubmit={async e=>{e.preventDefault();await onSave(draft);}}><label className="block text-xs font-medium">{label}<input className={`${input} mt-1`} value={draft} maxLength={200} disabled={disabled} onChange={e=>setDraft(e.target.value)}/></label>
    <div className="flex items-center justify-between gap-2">{source && <span className="text-[10px] text-muted">{source==="suggested"?"Suggested":source==="manual"?"Corrected by a member":<a href={`#message-${source}`} className="underline">From {author??"conversation"}</a>}</span>}{!disabled && draft!==value && <button disabled={!draft.trim()} className="ml-auto text-xs font-semibold text-brand">Save</button>}</div></form>;
}
function PlacesPicker() {
  const state=usePlanner()!;
  const [query,setQuery]=useState("");
  const [token,setToken]=useState("");
  const [results,setResults]=useState<{id:string;label:string}[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  return <div className="space-y-2"><form className="flex items-end gap-2" onSubmit={async e=>{e.preventDefault();setBusy(true);setError(""); const sessionToken=token||crypto.randomUUID();setToken(sessionToken);try {setResults(await apiFetch(`/trips/${state.planner!.tripId}/planner/places`,{method:"POST",body:JSON.stringify({query,sessionToken})}));}catch(cause){setError(cause instanceof Error?cause.message:"Place lookup unavailable");}finally{setBusy(false);}}}>
    <label className="min-w-0 flex-1 text-xs font-medium">Confirm an exact destination<input value={query} onChange={e=>setQuery(e.target.value)} className={`${input} mt-1`} placeholder={state.planner?.template.where.destinationHint??"Search Google Places"} minLength={2} maxLength={160}/></label><Button variant="outline" disabled={busy||query.length<2}>Search</Button></form>
    {error&&<p role="alert" className="text-xs text-amber-800">{error}</p>}{results.map(r=><button key={r.id} className="block w-full rounded-lg border border-line p-2 text-left text-xs hover:bg-surface" disabled={state.busy} onClick={async()=>{if(await state.destination(r.id,token)){setResults([]);setToken("");}}}>Use {r.label}</button>)}
  </div>;
}
export default function PlannerEditor() {
  const state=usePlanner()!;
  const [locationError,setLocationError]=useState("");
  if(state.loading) return <p role="status" className="p-5 text-sm">Loading planner…</p>;
  if(!state.planner) return <div className="space-y-3 p-5"><h2 className="text-lg font-semibold">Make a plan together</h2><p className="text-sm text-muted">Use + Planner in the chat to start Dining, Travel, or Entertainment.</p>{state.error&&<p role="alert">{state.error}</p>}<Button onClick={()=>state.setCreating(true)}>Start planner</Button><Button variant="outline" onClick={()=>void state.refresh()}>Refresh</Button></div>;
  const p=state.planner,t=p.template,uid=state.speaker;
  const frozen=p.status!=="collecting";
  const source=(field:string,personal=false)=>t.sources[`${field}:${personal?uid:"group"}`];
  const topicFields=p.topic==="Dining"?["meal_type","cuisine"]:p.topic==="Travel"?["trip_type","accommodation"]:["activity_type"];
  const availability=t.when.flexibility[uid];
  const availabilityLabel=availability===null?"Flexible":availability?.map(w=>w.label).join("; ")??"";
  const member=state.members[uid];
  const edit=(field:string,value:unknown)=>state.edit(field,value);
  const status=p.listening==="listening"||p.listening==="queued"?"Listening to the conversation…":p.listening==="failed"?"Listening unavailable. Retry or correct the template below.":p.poll.ready?"Ready for the group’s approval":frozen?"Criteria approved. Chat can continue.":"Building the plan as you talk";
  return <div className="space-y-5 p-5" aria-label="Live planner template">
    <div><p className="text-xs font-medium text-brand">{p.topic} planner</p><h2 className="text-xl font-semibold">{p.title}</h2><p role="status" className="mt-2 text-xs text-muted">{status}</p></div>
    {state.error&&<p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{state.error}</p>}
    {p.listening==="failed"&&<Button variant="outline" disabled={state.busy} onClick={()=>void state.action("retry")}>Retry listening</Button>}
    <section className="space-y-3"><h3 className="text-sm font-semibold">When and where</h3>
      <Editable key={`agreed-${t.when.agreed?.label}`} label="Agreed timing (optional if members supply availability)" value={t.when.agreed?.label??""} disabled={frozen} source={source("when.agreed")} onSave={value=>edit("when.agreed",value)}/>
      {t.when.agreed?.date&&<p className="text-xs">Confirmed date: {t.when.agreed.date} · {p.timezone}</p>}
      {t.where.destination?<div className="rounded-lg bg-surface p-3 text-sm"><strong>{t.where.destination.name}</strong><p className="text-xs text-muted">{t.where.destination.address}</p><p className="mt-1 text-xs">Human-confirmed destination</p></div>:<Editable key={`area-${t.where.searchArea}`} label="City or search area" value={t.where.searchArea??""} disabled={frozen} source={source("where.search_area")} onSave={value=>edit("where.search_area",value)}/>}
      {!frozen&&<PlacesPicker/>}
    </section>
    <section className={`space-y-3 rounded-xl border p-3 ${state.demoMode?"border-amber-300 bg-amber-50/40":"border-line"}`}><h3 className="text-sm font-semibold">{member?.name??"Your"}’s public details</h3>
      <div><p className="mb-2 text-xs font-medium">Attendance</p><div className="flex gap-2"><button disabled={frozen||state.busy} onClick={()=>void edit('attendance','going')} className={`rounded-lg border px-3 py-2 text-xs ${p.attendance[uid]?.status==='going'?'border-emerald-300 bg-emerald-50 text-emerald-800':'border-line'}`}>Going</button><button disabled={frozen||state.busy} onClick={()=>void edit('attendance','not_going')} className={`rounded-lg border px-3 py-2 text-xs ${p.attendance[uid]?.status==='not_going'?'border-rose-300 bg-rose-50 text-rose-800':'border-line'}`}>Not coming</button></div></div>
      <p className="text-[11px] text-muted">{p.attendance[uid]?.inferred?"Inferred from participation; you can correct this.":"Explicit attendance"}{p.attendance[uid]?.condition?` · ${p.attendance[uid].condition}`:""}</p>
      <Editable key={`${uid}-availability-${availabilityLabel}`} label="Availability (separate windows with ;)" value={availabilityLabel} disabled={frozen} source={source("when.flexibility",true)} onSave={value=>edit("when.flexibility",value.split(";").filter(Boolean).map(label=>({label:label.trim()})))}/>
      {!frozen&&<button className="text-xs font-semibold text-brand" disabled={state.busy} onClick={()=>void edit("when.flexibility",null)}>I’m flexible</button>}
      {([ ["preferences","Public preferences",t.preferences[uid]], ["hard_constraints","Public requirements",t.hardConstraints[uid]] ] as const).map(([field,label,values])=><Editable key={`${uid}-${field}-${values?.join(";")}`} label={label} value={values?.join("; ")??""} disabled={frozen} source={source(field,true)} onSave={value=>edit(field,value.split(";").map(s=>s.trim()).filter(Boolean))}/>)}
      <p className="text-[11px] text-muted">These details are shared with the group.</p>
      <Editable key={`${uid}-origin-${t.where.origins[uid]}`} label="Public origin city or confirmed airport (optional)" value={t.where.origins[uid]??""} disabled={frozen} source={source("where.origins",true)} onSave={value=>edit("where.origins",value)}/>
      {!frozen&&uid===state.me&&<button className="text-xs font-semibold text-brand" onClick={()=>{setLocationError("");const label=t.where.origins[uid];if(!label||/[0-9]/.test(label)){setLocationError("Enter your city label first. Only that label will be shared.");return;}if(!navigator.geolocation){setLocationError("Location unavailable; enter your city manually.");return;}navigator.geolocation.getCurrentPosition(async position=>{try{await apiFetch(`/trips/${p.tripId}/me/origin`,{method:"PUT",body:JSON.stringify({latitude:position.coords.latitude,longitude:position.coords.longitude,label})});await state.refresh();}catch(cause){setLocationError(cause instanceof Error?cause.message:"Could not save location");}},()=>setLocationError("Location permission unavailable; enter your city manually."),{timeout:10000,maximumAge:300000});}}>Use my device location (private)</button>}
      {locationError&&<p role="alert" className="text-xs text-amber-800">{locationError}</p>}
      {p.simpleFlow&&t.budget&&<Editable key={`${uid}-budget-${t.budget[uid]}`} label="Public spending limit (USD, optional)" value={t.budget[uid]?.toString()??''} disabled={frozen} source={source('budget',true)} onSave={value=>edit('budget',value.trim()?(Number.isFinite(Number(value))?Number(value):value):null)}/>}
    </section>
    <section><h3 className="mb-2 text-sm font-semibold">Group attendance</h3><ul className="space-y-2 text-xs">{Object.entries(p.attendance).map(([id,entry])=><li key={id} className="flex justify-between gap-2"><span>{state.members[id]?.name??"Member"}</span><span>{entry.status==='conditional'?'Yet to respond':entry.status==='going'?'Going':'Not coming'}{entry.inferred?" · inferred":""}</span></li>)}</ul></section>
    <section className="space-y-3"><h3 className="text-sm font-semibold">{p.topic} details <span className="font-normal text-muted">· optional</span></h3>{topicFields.map(field=><Editable key={`${field}-${JSON.stringify(t.cluster[field])}`} label={{meal_type:"Meal type",cuisine:"Cuisine (; separated)",trip_type:"Transport (flight or train)",accommodation:"Accommodation (hotel, airbnb, hostel, none)",activity_type:"Activity type"}[field]??field} value={Array.isArray(t.cluster[field])?(t.cluster[field] as string[]).join("; "):t.cluster[field] as string??""} disabled={frozen} source={source(field)} onSave={value=>edit(field,field==="cuisine"?value.split(";").map(s=>s.trim()).filter(Boolean):value)}/>)}</section>
    {!frozen&&<label className="block text-xs font-medium">Approval threshold<select className={`${input} mt-1`} value={p.poll.threshold} onChange={e=>void edit("threshold",Number(e.target.value))} disabled={state.busy}>{[.4,.5,.6].map(n=><option key={n} value={n}>{Math.round(n*100)}%</option>)}</select></label>}
    {!frozen&&!!p.missing.length&&<div className="rounded-lg bg-surface p-3 text-xs"><strong>Still needed</strong><ul className="mt-1 list-inside list-disc">{p.missing.map(item=><li key={item}>{item.startsWith("where.")?"A destination or city to search":item.startsWith("when.")?"Agreed timing, or availability from going members":item}</li>)}</ul></div>}



  </div>;
}
