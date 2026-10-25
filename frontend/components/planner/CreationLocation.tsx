"use client";
import { useEffect, useId, useState } from "react";
import { Check, MapPin } from "lucide-react";
import { apiFetch } from "@/lib/api";
export type ChosenPlace={placeId:string;sessionToken:string};
export default function CreationLocation({chatId,value,chosen,onChange,onChoose}:{chatId:string;value:string;chosen:ChosenPlace|null;onChange:(value:string)=>void;onChoose:(label:string,place:ChosenPlace)=>void}){
  const id=useId();
  const [token]=useState(()=>crypto.randomUUID());
  const [results,setResults]=useState<{id:string;label:string}[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [active,setActive]=useState(-1);
  useEffect(()=>{
    if(chosen||value.trim().length<3)return;
    let cancelled=false;
    const timer=setTimeout(async()=>{
      setBusy(true);setError("");
      try{const rows=await apiFetch<{id:string;label:string}[]>(`/chats/${chatId}/planner/places`,{method:"POST",body:JSON.stringify({query:value.trim(),sessionToken:token})});if(!cancelled)setResults(rows);}
      catch{if(!cancelled){setResults([]);setError("Maps search is unavailable. You can type a city or leave this empty.");}}
      finally{if(!cancelled)setBusy(false);}
    },400);
    return()=>{cancelled=true;clearTimeout(timer);};
  },[chatId,value,chosen,token]);
  const choose=(index:number)=>{const row=results[index];if(!row)return;onChoose(row.label,{placeId:row.id,sessionToken:token});setResults([]);setActive(-1);};
  return <div className="space-y-2"><label className="block text-xs font-medium" htmlFor={id}>Location <span className="font-normal text-muted">(optional)</span></label>
    <div className="relative"><MapPin size={15} className="absolute left-3 top-3.5 text-muted"/><input id={id} role="combobox" aria-label="Location (optional)" aria-autocomplete="list" aria-expanded={results.length>0} aria-controls={`${id}-results`} aria-activedescendant={active>=0?`${id}-${active}`:undefined} maxLength={200} value={value} onChange={e=>{onChange(e.target.value);setResults([]);setActive(-1);setError("");setBusy(false);}} onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();setActive(index=>Math.min(results.length-1,index+1));}if(e.key==='ArrowUp'){e.preventDefault();setActive(index=>Math.max(0,index-1));}if(e.key==='Enter'&&active>=0&&results.length){e.preventDefault();choose(active);}if(e.key==='Escape'&&results.length){e.stopPropagation();setResults([]);}}} placeholder="Search a city or exact place" className="w-full rounded-xl border border-line py-3 pl-9 pr-9 text-sm outline-none focus:border-violet-400"/>{chosen&&<Check size={15} className="absolute right-3 top-3.5 text-emerald-600"/>}</div>
    {!!results.length&&<ul id={`${id}-results`} role="listbox" aria-label="Location suggestions" className="max-h-40 overflow-y-auto rounded-xl border border-line bg-white p-1 shadow-sm">{results.map((row,index)=><li key={row.id} id={`${id}-${index}`} role="option" aria-selected={index===active}><button type="button" onMouseDown={e=>e.preventDefault()} onClick={()=>choose(index)} className={`w-full rounded-lg px-3 py-2 text-left text-xs ${index===active?'bg-violet-50':'hover:bg-surface'}`}>{row.label}</button></li>)}</ul>}
    {busy&&!chosen&&<p role="status" className="text-[11px] text-muted">Searching Google Maps…</p>}
    {error&&<p role="status" className="text-[11px] text-amber-800">{error}</p>}
    {chosen&&<p className="text-[11px] text-emerald-700">Selected from Google Maps</p>}
  </div>;
}
