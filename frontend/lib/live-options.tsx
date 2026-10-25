"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { apiFetch, ApiError } from "./api";
import { getClientSession } from "./supabase";
import type { Fact, Generation, Member, Option, PersistedTrip, PlanningInputs } from "./types";

const idle: Generation = { status: "idle", runId: null, message: null, missing: [], inputs: null, partial: false, optionCount: 0 };
type State = { scope: string; trip: PersistedTrip | null; options: Option[]; status: Generation; facts: Fact[];
  members: Record<string, Member>; me: string; loading: boolean; error: string | null };
type Context = State & { busy: boolean; refresh: () => Promise<void>; generate: (inputs?: PlanningInputs) => Promise<void>;
  pick: (id: string, acknowledge: boolean) => Promise<void>; create: () => Promise<void>; stage: (stage: string) => Promise<void>; vote: (going: boolean) => Promise<void> };
const Live = createContext<Context | null>(null);
const errorText = (error: unknown) => {
  if (error instanceof ApiError) {
    try { return JSON.parse(error.message).detail ?? "Request failed"; } catch { return "Request failed. Please retry."; }
  }
  return "Could not load this trip. Please retry.";
};

export function LiveOptionsProvider({ chatId = "", tripId = "", members = {}, me = "", children }: {
  chatId?: string; tripId?: string; members?: Record<string, Member>; me?: string; children: ReactNode;
}) {
  const scope = tripId ? `trip:${tripId}` : `chat:${chatId}`;
  const current = useRef(scope);
  current.current = scope;
  const serial = useRef(0);
  const initial: State = { scope, trip: null, options: [], status: idle, facts: [], members, me, loading: true, error: null };
  const [stored, setStored] = useState<State>(initial);
  const [pending, setPending] = useState(false);
  const state = stored.scope === scope ? stored : initial;
  const refresh = useCallback(async () => {
    if (!chatId && !tripId) return;
    const request = ++serial.current;
    try {
      const trip = await apiFetch<PersistedTrip | null>(tripId ? `/trips/${tripId}` : `/chats/${chatId}/trips/active`);
      const [options, status, facts, list] = trip ? await Promise.all([
        apiFetch<Option[]>(`/trips/${trip.id}/options`), apiFetch<Generation>(`/trips/${trip.id}/options/status`),
        apiFetch<Fact[]>(`/trips/${trip.id}/facts`), apiFetch<Member[]>(`/chats/${trip.chatId}/members`),
      ]) : [[], idle, [], []] as [Option[], Generation, Fact[], Member[]];
      const user = (await getClientSession())?.user.id ?? "";
      if (current.current !== scope || serial.current !== request) return;
      setStored({ scope, trip, options, status, facts, members: Object.fromEntries(list.map((m) => [m.id, m])),
        me: user, loading: false, error: null });
    } catch (error) {
      if (current.current === scope && serial.current === request)
        setStored((s) => ({ ...(s.scope === scope ? s : { scope, trip: null, options: [], status: idle, facts: [], members: {}, me: "" }), loading: false, error: errorText(error) }));
    }
  }, [chatId, tripId, scope]);
  useEffect(() => {
    void refresh();
    const changed = () => void refresh();
    window.addEventListener("instaplan:trip", changed);
    window.addEventListener("focus", changed);
    const counter = serial;
    return () => { counter.current++; window.removeEventListener("instaplan:trip", changed); window.removeEventListener("focus", changed); };
  }, [refresh]);
  useEffect(() => {
    const interval = setInterval(() => void refresh(), state.status.status === "generating" || state.status.status === "resolving" ? 1500 : 10000);
    return () => clearInterval(interval);
  }, [refresh, state.status.status]);
  const action = async (fn: () => Promise<unknown>) => {
    const actionScope = scope;
    setPending(true);
    try { await fn(); if (current.current === actionScope) await refresh(); }
    catch (error) { if (current.current === actionScope) setStored((s) => ({ ...s, error: errorText(error) })); }
    finally { if (current.current === actionScope) setPending(false); }
  };
  const generating = state.status.status === "resolving" || state.status.status === "generating";
  const value: Context = { ...state, members: Object.keys(members).length ? members : state.members, me: me || state.me,
    busy: pending || generating, refresh,
    generate: (inputs) => action(async () => {
      if (!state.trip) return;
      // Reflect the 202 immediately, avoiding a gap before polling begins.
      const status = await apiFetch<Generation>(`/trips/${state.trip.id}/options/generate`, { method: "POST", body: JSON.stringify({ inputs }) });
      if (current.current === scope) setStored((s) => ({ ...s, status }));
    }),
    pick: (id, acknowledge) => action(() => apiFetch(`/trips/${state.trip!.id}/pick`, {
      method: "POST", body: JSON.stringify({ optionId: id, acknowledgeCapacity: acknowledge }) })),
    create: () => action(() => apiFetch(`/chats/${chatId}/trips`, { method: "POST" })),
    stage: (stage) => action(() => apiFetch(`/trips/${state.trip!.id}/stage`, { method: "POST", body: JSON.stringify({ stage }) })),
    vote: (going) => action(() => apiFetch(`/trips/${state.trip!.id}/vote`, { method: "POST", body: JSON.stringify({ going }) })),
  };
  return <Live.Provider value={value}>{children}</Live.Provider>;
}
export const useLiveOptions = () => useContext(Live);
