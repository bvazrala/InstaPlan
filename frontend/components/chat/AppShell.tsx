"use client";

import { useState } from "react";
import { TripProvider, useTrip } from "@/lib/trip-context";
import { CHATS } from "@/mocks/demo-data";
import ChatList from "./ChatList";
import ChatThread from "./ChatThread";
import SidePanel from "./SidePanel";
import MobileSheet from "./MobileSheet";
import NavRail from "./NavRail";
import { INITIAL_UNREAD } from "./chat-meta";

function Shell() {
  const { panelOpen, setActiveChat } = useTrip();
  const [chatId, setChatId] = useState("crew");
  const [read, setRead] = useState<string[]>(["crew"]);
  const [mobileView, setMobileView] = useState<"list" | "thread">("thread");
  const chat = CHATS.find((c) => c.id === chatId)!;

  const unreadIds = INITIAL_UNREAD.filter((id) => !read.includes(id) && id !== chatId);
  const open = (id: string) => {
    setChatId(id);
    setActiveChat(id);
    setMobileView("thread");
    setRead((r) => (r.includes(id) ? r : [...r, id]));
  };

  return (
    <div className="flex h-dvh bg-white text-foreground">
      <NavRail
        unread={unreadIds.length}
        onMessages={() => setMobileView("list")}
      />
      <aside className={`${mobileView === "list" ? "flex" : "hidden"} w-full flex-col md:flex md:w-[360px] md:shrink-0 md:border-r md:border-line`}>
        <ChatList chats={CHATS} activeId={chatId} unreadIds={unreadIds} onSelect={open} />
      </aside>
      <main className={`${mobileView === "thread" ? "flex" : "hidden"} min-w-0 flex-1 flex-col md:flex`}>
        <ChatThread key={chat.id} chat={chat} onBack={() => setMobileView("list")} />
      </main>
      <aside className={`${panelOpen && chat.group ? "lg:block" : ""} hidden w-[400px] shrink-0 border-l border-line`}>
        <SidePanel />
      </aside>
      {chat.group && <MobileSheet />}
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
