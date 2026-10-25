"use client";
import { useEffect, useState } from "react";
import { usePlanner } from "@/lib/planner-context";
import { apiFetch } from "@/lib/api";
import type { WidgetSpecial } from "@/lib/types";
import DemoExpenseSplit from "../DemoExpenseSplit";
import { PlanWidget } from "./PlanWidget";
import { venueDeck, stayDeck } from "./adapters";
import { selectWidgetDeck } from "./widget-rules";
import type { WidgetDeck, SpecialCardData } from "./widget-types";
export default function ChatPlanWidget({onOpen,embedded=false}:{onOpen:()=>void;embedded?:boolean}){
  const state=usePlanner()!;
  const [flight,setFlight]=useState<{optionId:string;runId:string|null;data:SpecialCardData}|null>(null);
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState("");
  const p=state.planner!;
  const active=p.generation.status==="resolving"||p.generation.status==="generating";
  const rec=p.recommendations;
  const option=rec.kind==="travel"?(rec.options.find(o=>o.id===p.pickedId)??rec.options[0]):null;
  const venue=rec.kind==="venues"?(rec.venues.find(v=>v.id===p.pickedId)??rec.venues[0]):null;
  let deck:WidgetDeck=option?stayDeck(option):venue?venueDeck(venue,p.topic):{slides:[],reason:"no_provider_result"};
  const mine=option?.people.find(person=>person.id===state.me);
  const optionId=option?.id??null;
  const hasImage=!!option?.imageUrl;
  const myOrigin=mine?.origin??null;
  const tripId=p.tripId,runId=p.generation.runId,viewerId=state.me;
  useEffect(()=>{
    if(active||!optionId||!hasImage||!myOrigin||!navigator.permissions)return;
    let cancelled=false;
    let permission:PermissionStatus|undefined;
    void navigator.permissions.query({name:'geolocation'}).then(async status=>{
      permission=status;
      const changed=()=>{if(status.state!=='granted')setFlight(null);};
      status.onchange=changed;
      if(cancelled){status.onchange=null;return;}
      if(status.state!=='granted')return;
      try{
        const reply=await apiFetch<{special:WidgetSpecial|null}>(`/trips/${tripId}/me/widget/flight`,{method:'POST',body:JSON.stringify({optionId,locationGranted:true})});
        const special=reply.special;
        if(!cancelled&&special?.kind==='flight'&&special.forViewerId===viewerId)setFlight({optionId,runId,data:{...special,forViewerId:special.forViewerId??undefined,originCode:special.originCode??undefined,destinationCode:special.destinationCode??undefined}});
      }catch{/* A missing flight quote keeps the sourced stay fallback. */}
    }).catch(()=>{});
    return()=>{cancelled=true;if(permission)permission.onchange=null;};
  },[active,optionId,hasImage,myOrigin,tripId,runId,viewerId]);
  if(option&&flight?.optionId===option.id&&flight.runId===p.generation.runId&&deck.slides[0]?.kind==="fallback"){
    deck=selectWidgetDeck({fallback:deck.slides[0].data,special:flight.data,viewer:{viewerId:state.me,confirmedOrigin:mine?.origin??null,locationPermission:"granted"}});
  }
  if(!active&&!deck.slides.length)return <div className="mt-3 text-xs text-muted">{p.generation.status==='failed'?<><p>Recommendations need a retry.</p><button className="mt-2 font-semibold text-violet-700" onClick={()=>void state.action('retry')}>Retry recommendation</button></>:p.generation.status==='ready'?<p>No matching place was found. Revise the plan or retry.</p>:null}</div>;
  const showFlight=()=>{
    if(!option||!mine?.origin)return;
    setBusy(true);setNotice("");
    if(!navigator.geolocation){setNotice("Location is unavailable. Your stay card is still here.");setBusy(false);return;}
    // Permission is deliberate. Coordinates are never sent to this widget endpoint.
    navigator.geolocation.getCurrentPosition(async()=>{
      try{
        const reply=await apiFetch<{special:WidgetSpecial|null}>(`/trips/${p.tripId}/me/widget/flight`,{method:"POST",body:JSON.stringify({optionId:option.id,locationGranted:true})});
        const special=reply.special;
        if(special?.kind==="flight"&&special.forViewerId===state.me){setFlight({optionId:option.id,runId:p.generation.runId,data:{...special,forViewerId:special.forViewerId??undefined,originCode:special.originCode??undefined,destinationCode:special.destinationCode??undefined}});}
        else setNotice("A verified flight booking link or image isn’t available. You can still compare the quoted flights in the plan.");
      }catch{setNotice("Flight details are unavailable right now. Your stay card is still here.");}
      finally{setBusy(false);}
    },()=>{setNotice("Location wasn’t enabled. Your stay card is still here.");setBusy(false);},{timeout:10000,maximumAge:300000});
  };
  return <div className="mt-4 max-w-[338px] space-y-3" aria-label="Plan widget result">
    <p className="text-[11px] font-medium text-muted">{active?"Finding an idea for your plan…":p.pickedId?"Your group’s selection":"Your recommended choice"}</p>
    <PlanWidget deck={deck} loading={active} animationKey={p.generation.runId??p.approvalRevision}/>
    {mine&&!active&&<button className="text-xs font-semibold text-violet-700" onClick={showFlight} disabled={busy}>{busy?"Checking your flight…":"Show my flight card"}</button>}
    {option?.capacityAckRequired&&<p className="text-[11px] leading-relaxed text-muted">Confirm lodging capacity with the listing before booking.</p>}
    {venue&&<p className="text-[11px] leading-relaxed text-muted">Confirm current prices and availability with the provider.</p>}
    {notice&&<p role="status" className="text-xs leading-relaxed text-muted">{notice}</p>}
    {!embedded&&!active&&state.demoMode&&(venue||option)&&<DemoExpenseSplit key={`${p.tripId}:${p.approvalRevision}:${venue?.id??option?.id}`} place={venue?.title??option?.lodging??p.title}/>}
    {!embedded&&<button className="text-xs font-semibold text-violet-700" onClick={onOpen}>Plan details →</button>}
  </div>;
}
