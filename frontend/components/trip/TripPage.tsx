"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { LiveOptionsProvider, useLiveOptions } from "@/lib/live-options";
import { PlannerProvider, usePlanner } from "@/lib/planner-context";
import { apiFetch, ApiError } from "@/lib/api";
import { getClientSession } from "@/lib/supabase";
import type { Member, Planner, PersistedTrip } from "@/lib/types";
import PlannerRecommendations from "@/components/planner/PlannerRecommendations";
import OptionsView from "./options/OptionsView";
function LegacyContent() {
  const live = useLiveOptions()!;
  return <><h1 className="mb-4 font-semibold">Trip options · {live.options[0]?.dates??"flights and lodging"}</h1><OptionsView wide/></>;
}
function PlannerContent() {
  const state=usePlanner()!;
  if(state.loading) return <p role="status">Loading plan…</p>;
  if(!state.planner) return <p role="alert">{state.error??"Planner unavailable"}</p>;
  return <><div className="mb-5"><p className="text-xs text-brand">{state.planner.topic} planner</p><h1 className="text-2xl font-semibold">{state.planner.title}</h1></div>{state.error&&<p role="alert" className="mb-3 text-sm text-red-700">{state.error}</p>}{state.planner.status==="collecting"?<p>Return to the chat to complete and approve this revision.</p>:<PlannerRecommendations wide/>}</>;
}
export default function TripPage({tripId}:{tripId:string}) {
  const [data,setData]=useState<{unified:boolean;chatId:string;me:string;demoMode:boolean;members:Record<string,Member>}|null>(null);
  const [error,setError]=useState("");
  useEffect(()=>{let cancelled=false;void(async()=>{try{
    const session=await getClientSession();
    const trip=await apiFetch<PersistedTrip>(`/trips/${tripId}`);
    const members=await apiFetch<Member[]>(`/chats/${trip.chatId}/members`);
    let unified=false;
    try{await apiFetch<Planner>(`/trips/${tripId}/planner`);unified=true;}catch(cause){if(!(cause instanceof ApiError)||cause.status!==404) throw cause;}
    if(!cancelled)setData({unified,chatId:trip.chatId,me:session?.user.id??"",demoMode:session?.demoMode??false,members:Object.fromEntries(members.map(m=>[m.id,m]))});
  }catch(cause){if(!cancelled)setError(cause instanceof Error?cause.message:"Could not load plan");}})();return()=>{cancelled=true;};},[tripId]);
  return <div className="min-h-dvh bg-[#f7f7f8]"><header className="sticky top-0 z-10 flex min-h-14 items-center gap-3 border-b border-line bg-white px-4 py-3"><Link href="/" className="flex items-center gap-2 text-sm" aria-label="Back to chat"><ArrowLeft size={20}/>Back to chat</Link></header><main className="mx-auto max-w-[1400px] p-4 md:p-6">
    {error?<p role="alert">{error}</p>:!data?<p role="status">Loading comparison…</p>:data.unified?<PlannerProvider key={tripId} tripId={tripId} chatId={data.chatId} members={data.members} me={data.me} demoMode={data.demoMode}><PlannerContent/></PlannerProvider>:<LiveOptionsProvider key={tripId} tripId={tripId} members={data.members} me={data.me}><LegacyContent/></LiveOptionsProvider>}
  </main></div>;
}
