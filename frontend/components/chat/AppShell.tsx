"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TripProvider, useTrip } from "@/lib/trip-context";
import { apiFetch } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { Chat, ChatMessage, Member } from "@/lib/types";
import ChatList from "./ChatList";
import ChatThread from "./ChatThread";
import SidePanel from "./SidePanel";
import MobileSheet from "./MobileSheet";
import NavRail from "./NavRail";

type ApiChat = { id: string; name: string; group: boolean; members: string[] };

function Shell() {
  const router = useRouter();
  const { panelOpen, setActiveChat } = useTrip();
  const [chatId, setChatId] = useState("");
  const [chats, setChats] = useState<Chat[]>([]);
  const [members, setMembers] = useState<Record<string, Member>>({});
  const [lastMessages, setLastMessages] = useState<Record<string, ChatMessage>>({});
  const [me, setMe] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"list" | "thread">("thread");
  const chat = chats.find((c) => c.id === chatId);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!supabase) {
        setError("Supabase login is not configured. Add the public settings to frontend/.env.local.");
        return;
      }
      const session = (await supabase.auth.getSession()).data.session;
      if (!session) {
        router.replace("/login");
        return;
      }
      try {
        const found = await apiFetch<ApiChat[]>("/chats");
        const lists = await Promise.all(found.map((c) => apiFetch<Member[]>(`/chats/${c.id}/members`)));
        if (cancelled) return;
        setMe(session.user.id);
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
    <div className="flex h-dvh bg-white text-foreground">
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
        <SidePanel />
      </aside>
      {chat?.group && <MobileSheet />}
    </div>
  );
}

export default function AppShell() {
  return (
    <TripProvider>
      <Shell />
    </TripProvider>
  );
}
