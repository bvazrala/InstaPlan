"use client";
import { useState } from "react";
import { usePlanner } from "@/lib/planner-context";
import { sortOptions } from "@/lib/sort";
import type { PlanningInputs, SortKey } from "@/lib/types";
import OptionCard from "@/components/trip/options/OptionCard";
import { Button } from "@/components/ui/primitives";

function PricingForm() {
  const state=usePlanner()!,p=state.planner!;
  const saved=p.generation.inputs;
  const location=p.template.where.destination?.name??p.template.where.searchArea??"";
  const [inputs,setInputs]=useState<PlanningInputs>(saved??{destinations:[],checkin:p.template.when.agreed?.date??null,checkout:null,origins:{}});
  const [airport,setAirport]=useState(saved?.destinations[0]?.airports[0]??"");
  const cls="mt-1 w-full rounded-lg border border-line p-2 text-sm";
  return <form className="space-y-3 rounded-xl border border-line bg-white p-3" onSubmit={e=>{e.preventDefault();void state.pricing({...inputs,destinations:[{name:location,airports:[airport.toUpperCase()]}]});}}>
    <h3 className="text-sm font-semibold">Confirm flight search details</h3><p className="text-xs text-muted">The plan can be flexible. Flight pricing needs exact dates and confirmed airports. Device location does not choose an airport.</p>
    <p className="text-xs font-medium">Approved destination: {location}</p>
    <label className="block text-xs">Arrival airport<input aria-label="Arrival airport" required pattern="[A-Za-z]{3}" maxLength={3} value={airport} onChange={e=>setAirport(e.target.value)} className={cls} placeholder="JFK"/></label>
    <div className="grid grid-cols-2 gap-2"><label className="text-xs">Outbound date<input aria-label="Outbound date" type="date" required value={inputs.checkin??""} onChange={e=>setInputs({...inputs,checkin:e.target.value})} className={cls}/></label><label className="text-xs">Return date<input aria-label="Return date" type="date" required value={inputs.checkout??""} onChange={e=>setInputs({...inputs,checkout:e.target.value})} className={cls}/></label></div>
    {p.pricedMembers.map(id=><label key={id} className="block text-xs">{state.members[id]?.name??"Member"} departure airport<input aria-label={`${state.members[id]?.name??id} departure airport`} required pattern="[A-Za-z]{3}" maxLength={3} value={inputs.origins[id]??""} onChange={e=>setInputs({...inputs,origins:{...inputs.origins,[id]:e.target.value.toUpperCase()}})} className={cls}/></label>)}
    <Button disabled={state.busy||!p.pricedMembers.length}>Find flight and lodging options</Button>
  </form>;
}
export default function PlannerRecommendations({wide=false}:{wide?:boolean}) {
  const state=usePlanner()!,p=state.planner!;
  const [sort,setSort]=useState<SortKey>("balanced");
  const [weight,setWeight]=useState(.5);
  const [venueOrder,setVenueOrder]=useState<"fit"|"rating">("fit");
  const g=p.generation,active=g.status==="resolving"||g.status==="generating";
  const rec=p.recommendations;
  const count=rec.kind==="travel"?rec.options.length:rec.venues.length;
  return <section className="space-y-4" aria-label="Recommendations">
    <h3 className="font-semibold">{p.status==="picked"?"Selected plan":"Recommendations"}</h3>
    {active&&<p role="status" className="rounded-lg bg-violet-50 p-3 text-sm">{g.status==="resolving"?"Checking the approved plan…":"Finding recommendations…"}</p>}
    {g.status==="failed"&&<div role="alert" className="space-y-2 rounded-lg bg-amber-50 p-3 text-sm"><p>{g.message??"Recommendations unavailable. Previous results are preserved."}</p><Button variant="outline" disabled={state.busy} onClick={()=>void state.action("retry")}>Retry recommendations</Button></div>}
    {g.partial&&<p className="text-xs text-amber-800">Partial results: some provider searches were unavailable.</p>}
    {g.status==="needs_input"&&<p role="status" className="text-sm text-amber-800">{g.message??"Confirm the missing search details."}</p>}
    {rec.kind==="travel"&&g.status==="needs_input"&&<PricingForm key={g.runId}/>}
    {g.status==="ready"&&!count&&<p role="status" className="rounded-lg bg-surface p-3 text-sm">No matching recommendations were found. Revise the plan or retry the search.</p>}
    {p.status==='approved'&&!active&&g.status==='ready'&&<Button variant="outline" disabled={state.busy} onClick={()=>void state.action("retry")}>Refresh recommendations</Button>}
    {rec.kind==="travel"&&!!count&&<>
      <label className="block text-xs font-medium">Sort options<select className="ml-2 rounded-lg border border-line p-2" value={sort} onChange={e=>setSort(e.target.value as SortKey)}>{["cheapest","fastest","balanced","fairest"].map(key=><option key={key} value={key}>{key[0].toUpperCase()+key.slice(1)}</option>)}</select></label>
      {sort==="balanced"&&<label className="block text-xs">Balance: {Math.round(weight*100)}% cost · {Math.round((1-weight)*100)}% travel time<input aria-label="Cost weight" className="mt-2 w-full" type="range" min="0" max="1" step=".05" value={weight} onChange={e=>setWeight(Number(e.target.value))}/></label>}
      <div className={wide?"grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3":"space-y-4"}>{sortOptions(rec.options,sort,weight).map((o,i)=><OptionCard key={o.id} o={o} rank={i} members={state.members} me={state.me} picked={p.pickedId===o.id} disabled={state.busy||active||p.status==="picked"} onPick={ack=>void state.pick(o.id,ack)}/>)}</div>
    </>}
    {rec.kind==="venues"&&!!count&&<><label className="block text-xs">Order<select aria-label="Venue ordering" value={venueOrder} onChange={e=>setVenueOrder(e.target.value as "fit"|"rating")} className="ml-2 rounded-lg border border-line p-2"><option value="fit">Group fit, then rating</option><option value="rating">Rating</option></select></label>
      <div className={wide?"grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3":"space-y-4"}>{[...rec.venues].sort((a,b)=>(venueOrder==="fit"?(b.fit??-1)-(a.fit??-1):0)||((b.rating??-1)-(a.rating??-1))||(a.id<b.id?-1:1)).map(v=><article key={v.id} aria-label={v.title} className={`space-y-3 rounded-xl border bg-white p-4 ${p.pickedId===v.id?"border-brand":"border-line"}`}><div><h4 className="font-semibold">{v.title}</h4><p className="text-xs text-muted">{v.address??"Address unavailable"}</p></div><div className="flex gap-4 text-sm"><span>★ {v.rating??"Unknown"}</span><span>Fit {v.fit==null?"unknown":`${v.fit}%`}</span><span>{v.priceLevel?`Price level ${v.priceLevel}`:"Price unknown"}</span></div>
      {!!v.evidence.length&&<ul className="space-y-1 text-xs">{v.evidence.map(e=><li key={e}>{e}</li>)}</ul>}<ul className="space-y-1 text-xs text-muted">{v.warnings.map(w=><li key={w}>{w}</li>)}</ul><p className="text-[10px] text-muted">{v.provider} · retrieved {new Date(v.retrievedAt).toLocaleString()}</p>
      {v.url&&/^https?:\/\//.test(v.url)&&<a href={v.url} target="_blank" rel="noreferrer" className="block text-xs font-semibold text-brand">View venue ↗</a>}
      <Button disabled={state.busy||active||!v.pickEligible||p.status==="picked"} onClick={()=>void state.pick(v.id)}>{p.pickedId===v.id?"Selected":v.pickEligible?"Pick this venue":"Verification needed"}</Button></article>)}</div></>}
  </section>;
}
