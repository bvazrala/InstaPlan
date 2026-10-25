"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TripProvider, useTrip } from "@/lib/trip-context";
import { useIsDesktop } from "@/lib/use-desktop";
import { PlannerProvider } from "@/lib/planner-context";
import { apiFetch } from "@/lib/api";
import { getClientSession, supabaseConfigured } from "@/lib/supabase";
import type { Chat, ChatMessage, Member } from "@/lib/types";
import ChatList from "./ChatList";
import ChatThread from "./ChatThread";
import SidePanel from "./SidePanel";
import MobileSheet from "./MobileSheet";
import NavRail from "./NavRail";

type ApiChat = { id: string; name: string; group: boolean; members: string[] };

function Shell() {
  const router = useRouter();
  const desktop = useIsDesktop();
  const { panelOpen, setActiveChat } = useTrip();
  const [chatId, setChatId] = useState("");
  const [chats, setChats] = useState<Chat[]>([]);
  const [members, setMembers] = useState<Record<string, Member>>({});
  const [lastMessages, setLastMessages] = useState<Record<string, ChatMessage>>({});
  const [me, setMe] = useState("");
  const [demoMode, setDemoMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"list" | "thread">("thread");
  const chat = chats.find((c) => c.id === chatId);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const session = await getClientSession();
        if (cancelled) return;
        if (!session) {
          if (!supabaseConfigured) setError("Start the local demo backend or configure Supabase login.");
          else router.replace("/login");
          return;
        }
        const found = await apiFetch<ApiChat[]>("/chats");
        const lists = await Promise.all(found.map((c) => apiFetch<Member[]>(`/chats/${c.id}/members`)));
        if (cancelled) return;
        setMe(session.user.id);
        setDemoMode(session.demoMode);
        setMembers(Object.fromEntries(lists.flat().map((member) => [member.id, member])));
        setChats(found.map((c) => ({ ...c, sub: `${c.members.length} members` })));
        if (found.length) {
          setChatId(found[0].id);
          setActiveChat(found[0].id);
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load chats");
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [router, setActiveChat]);

  const unreadIds: string[] = [];
  const open = (id: string) => {
    setChatId(id);
    setActiveChat(id);
    setMobileView("thread");
  };
  const onLatest = useCallback((id: string, message: ChatMessage) => {
    setLastMessages((current) => current[id]?.sentAt > message.sentAt ? current : { ...current, [id]: message });
  }, []);

  if (error) return <div role="alert" className="flex min-h-dvh items-center justify-center p-6 text-sm text-red-700">{error}</div>;
  if (!me) return <div className="flex min-h-dvh items-center justify-center text-sm text-muted">Loading chats…</div>;

  return (
    <PlannerProvider key={chatId} chatId={chatId} members={Object.fromEntries((chat?.members??[]).map(id=>[id,members[id]]).filter(([,member])=>!!member))} me={me} demoMode={demoMode}>
    <div className="flex h-dvh flex-col">
    {demoMode && <div role="status" className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900">Local demo · sample people · saved on this computer</div>}
    <div className="flex min-h-0 flex-1 bg-white text-foreground">
      <NavRail
        unread={unreadIds.length}
        onMessages={() => setMobileView("list")}
      />
      <aside className={`${mobileView === "list" ? "flex" : "hidden"} w-full flex-col md:flex md:w-[360px] md:shrink-0 md:border-r md:border-line`}>
        <ChatList chats={chats} activeId={chatId} unreadIds={unreadIds} onSelect={open} members={members} me={me} lastMessages={lastMessages} />
      </aside>
      <main className={`${mobileView === "thread" ? "flex" : "hidden"} min-w-0 flex-1 flex-col md:flex`}>
        {chat && <ChatThread key={chat.id} chat={chat} me={me} members={members} onLatest={onLatest} onBack={() => setMobileView("list")} />}
      </main>
      <aside className={`${panelOpen && chat?.group ? "lg:block" : ""} hidden w-[400px] shrink-0 border-l border-line`}>
        {desktop && <SidePanel />}
      </aside>
      {!desktop && chat?.group && <MobileSheet />}
    </div>
    </div>
    </PlannerProvider>
  );
}

export default function AppShell() {
  return (
    <TripProvider>
      <Shell />
    </TripProvider>
  );
}
