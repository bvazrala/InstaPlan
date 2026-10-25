"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { apiFetch } from "./api";
import type { Member, Planner, PlannerTopic, PlanningInputs } from "./types";

type PlannerState = {
  planner: Planner | null; loading: boolean; busy: boolean; error: string | null;
  chatId: string; me: string; members: Record<string, Member>; demoMode: boolean;
  speaker: string; setSpeaker: (id: string) => void; creating: boolean; setCreating: (value: boolean) => void;
  refresh: () => Promise<void>; create: (title: string, topic: PlannerTopic, location: string) => Promise<boolean>;
  edit: (field: string, value: unknown) => Promise<boolean>; vote: (approve: boolean) => Promise<boolean>;
  action: (name: "revise" | "retry") => Promise<boolean>; pricing: (inputs: PlanningInputs) => Promise<boolean>;
  pick: (id: string, acknowledgeCapacity?: boolean) => Promise<boolean>;
  destination: (placeId: string, sessionToken: string) => Promise<boolean>;
};
const Context = createContext<PlannerState | null>(null);
export function usePlanner() { return useContext(Context); }
export function PlannerProvider({ children, chatId = "", tripId, me = "", members = {}, demoMode = false }: {
  children: ReactNode; chatId?: string; tripId?: string; me?: string; members?: Record<string, Member>; demoMode?: boolean;
}) {
  const [planner, setPlanner] = useState<Planner | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [speaker, setSpeaker] = useState(me);
  const [creating, setCreating] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const refresh = useCallback(async () => {
    if (!chatId && !tripId) return;
    try {
      const next = await apiFetch<Planner | null>(tripId ? `/trips/${tripId}/planner` : `/chats/${chatId}/planner`);
      if (mounted.current) { setPlanner(current => current && next && current.tripId === next.tripId && current.revision > next.revision ? current : next); }
    } catch (cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : "Could not load planner"); }
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
  const request = async (path: string, body?: unknown, method = "POST") => {
    setBusy(true); setError(null);
    try {
      const next = await apiFetch<Planner>(path, {method, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
      if (mounted.current) setPlanner(next);
      window.dispatchEvent(new Event("instaplan:trip"));
      return true;
    } catch (cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : "Could not update plan"); return false; }
    finally { if (mounted.current) setBusy(false); }
  };
  const base = `/trips/${planner?.tripId}/planner`;
  const perspective = demoMode ? {demoSpeakerId:speaker || me} : {};
  return <Context.Provider value={{planner, loading, busy, error, chatId, me, members, demoMode,
    speaker: speaker || me, setSpeaker, creating, setCreating, refresh,
    create: (title, topic, location) => request(`/chats/${chatId}/planners`, {title,topic,location,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone}),
    edit: (field,value) => request(base,{revision:planner?.revision,field,value,...perspective},"PATCH"),
    vote: (approve) => request(`${base}/approve`,{revision:planner?.approvalRevision,approve,...perspective}),
    action: (name) => request(`${base}/${name}`), pricing: (inputs) => request(`${base}/pricing`,{inputs}),
    pick: (id,acknowledgeCapacity=false) => request(`${base}/pick`,{optionId:id,acknowledgeCapacity}),
    destination: (placeId,sessionToken) => request(`${base}/destination`,{placeId,sessionToken,revision:planner?.revision}),
  }}>{children}</Context.Provider>;
}
