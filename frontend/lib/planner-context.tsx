"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { apiFetch } from "./api";
import type { Member, Planner, PlannerTopic, PlanningInputs } from "./types";

type PlannerState = {
  planner: Planner | null; loading: boolean; busy: boolean; error: string | null;
  chatId: string; me: string; members: Record<string, Member>; demoMode: boolean;
  speaker: string; setSpeaker: (id: string) => void; creating: boolean; setCreating: (value: boolean) => void;
  refresh: () => Promise<void>; create: (title: string, topic: PlannerTopic, location: string, place?:{placeId:string;sessionToken:string}) => Promise<boolean>;
  reset:()=>Promise<void>;
  respond:(going:boolean)=>Promise<boolean>;
  edit: (field: string, value: unknown) => Promise<boolean>; vote: (approve: boolean) => Promise<boolean>;
  action: (name: "revise" | "retry") => Promise<boolean>; pricing: (inputs: PlanningInputs) => Promise<boolean>;
  pick: (id: string, acknowledgeCapacity?: boolean) => Promise<boolean>;
  destination: (placeId: string, sessionToken: string) => Promise<boolean>;
};
function message(cause: unknown, fallback: string) {
  if (!(cause instanceof Error)) return fallback;
  try { const detail = JSON.parse(cause.message).detail; return typeof detail === 'string' ? detail : 'Check the entered fields and try again.'; }
  catch { return cause.message === 'Failed to fetch' ? 'Could not reach InstaPlan. Please retry.' : cause.message; }
}
const Context = createContext<PlannerState | null>(null);
export function usePlanner() { return useContext(Context); }
function PlannerSessionProvider({ children, chatId = "", tripId, me = "", members = {}, demoMode = false }: {
  children: ReactNode; chatId?: string; tripId?: string; me?: string; members?: Record<string, Member>; demoMode?: boolean;
}) {
  const [planner, setPlanner] = useState<Planner | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [speaker, setSpeaker] = useState(me);
  const [creating, setCreating] = useState(false);
  const mounted = useRef(true);
  const epoch=useRef(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const refresh = useCallback(async () => {
    if (!chatId && !tripId) return;
    const requestEpoch=epoch.current;
    try {
      const next = await apiFetch<Planner | null>(tripId ? `/trips/${tripId}/planner` : `/chats/${chatId}/planner`);
      if (mounted.current && requestEpoch===epoch.current) { setPlanner(current => current && next && current.tripId === next.tripId && current.revision > next.revision ? current : next); setLoadError(null); }
    } catch (cause) { if (mounted.current) setLoadError(message(cause,"Could not load planner")); }
    finally { if (mounted.current) setLoading(false); }
  }, [chatId, tripId]);
  useEffect(() => {
    const initial = setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), 1500);
    const update = () => void refresh();
    window.addEventListener("instaplan:trip", update);
    window.addEventListener("online", update);
    return () => { clearTimeout(initial); clearInterval(timer); window.removeEventListener("instaplan:trip", update); window.removeEventListener("online", update); };
  }, [refresh]);
  useEffect(()=>{
    const resetReceived=(event:Event)=>{
      const detail=(event as CustomEvent<{chatId:string}>).detail;
      if(detail.chatId!==chatId)return;
      epoch.current++;setPlanner(null);setCreating(false);setSpeaker(me);
      void refresh();
    };
    window.addEventListener('instaplan:chat-reset',resetReceived);
    return()=>window.removeEventListener('instaplan:chat-reset',resetReceived);
  },[chatId,me,refresh]);
  const request = async (path: string, body?: unknown, method = "POST") => {
    const requestEpoch=epoch.current;
    setBusy(true); setError(null);
    try {
      const next = await apiFetch<Planner>(path, {method, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
      if (mounted.current&&requestEpoch===epoch.current) setPlanner(next);
      window.dispatchEvent(new Event("instaplan:trip"));
      return true;
    } catch (cause) { if (mounted.current) setError(message(cause,"Could not update plan")); return false; }
    finally { if (mounted.current) setBusy(false); }
  };
  const reset = async()=>{
    epoch.current++;
    setBusy(true);setError(null);
    try{
      const result=await apiFetch<{resetAt:string}>(`/chats/${chatId}/demo/reset`,{method:'POST'});
      epoch.current++;setPlanner(null);setCreating(false);setSpeaker(me);
      window.dispatchEvent(new CustomEvent('instaplan:chat-reset',{detail:{chatId,resetAt:result.resetAt}}));
      window.dispatchEvent(new Event('instaplan:trip'));
    }catch(cause){setError(message(cause,'Could not reset the demo.'));}
    finally{setBusy(false);}
  };
  const base = `/trips/${planner?.tripId}/planner`;
  const perspective = demoMode ? {demoSpeakerId:speaker || me} : {};
  return <Context.Provider value={{planner, loading, busy, error: error ?? loadError, chatId, me, members, demoMode,
    speaker: speaker || me, setSpeaker, creating, setCreating, refresh,
    reset, respond:(going)=>request(`${base}/respond`,{revision:planner?.approvalRevision,going,...perspective}),
    create: (title, topic, location, place) => request(`/chats/${chatId}/planners`, {title,topic,location,...place,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone}),
    edit: (field,value) => request(base,{revision:planner?.revision,field,value,...perspective},"PATCH"),
    vote: (approve) => request(`${base}/approve`,{revision:planner?.approvalRevision,approve,...perspective}),
    action: (name) => request(`${base}/${name}`), pricing: (inputs) => request(`${base}/pricing`,{inputs}),
    pick: (id,acknowledgeCapacity=false) => request(`${base}/pick`,{optionId:id,acknowledgeCapacity}),
    destination: (placeId,sessionToken) => request(`${base}/destination`,{placeId,sessionToken,revision:planner?.revision}),
  }}>{children}</Context.Provider>;
}


export function PlannerProvider(props: Parameters<typeof PlannerSessionProvider>[0]) {
  return <PlannerSessionProvider key={`${props.chatId ?? ''}:${props.tripId ?? ''}:${props.me ?? ''}`} {...props}/>;
}
