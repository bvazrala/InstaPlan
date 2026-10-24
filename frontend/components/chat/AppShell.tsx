"use client";

import { useState } from "react";
import { TripProvider } from "@/lib/trip-context";
import { CHATS } from "@/mocks/demo-data";
import ChatList from "./ChatList";
import ChatThread from "./ChatThread";
import SidePanel from "./SidePanel";
import MobileSheet from "./MobileSheet";
import TopBar from "./TopBar";

export default function AppShell() {
  const [chatId, setChatId] = useState("crew");
  const [mobileView, setMobileView] = useState<"list" | "thread">("thread");
  const chat = CHATS.find((c) => c.id === chatId)!;

  return (
    <TripProvider>
      <div className="flex h-dvh flex-col bg-white md:bg-[#f7f7f8]">
        <TopBar />
        <div className="flex min-h-0 flex-1 gap-4 md:p-4">
          <aside className={`${mobileView === "list" ? "flex" : "hidden"} w-full flex-col md:flex md:w-[270px] md:shrink-0`}>
            <ChatList activeId={chatId} onSelect={(id) => { setChatId(id); setMobileView("thread"); }} />
          </aside>
          <main className={`${mobileView === "thread" ? "flex" : "hidden"} min-w-0 flex-1 flex-col md:flex`}>
            <ChatThread chat={chat} onBack={() => setMobileView("list")} />
          </main>
          <aside className="hidden w-[300px] shrink-0 lg:block xl:w-[320px]">
            <SidePanel />
          </aside>
        </div>
        <MobileSheet />
      </div>
    </TripProvider>
  );
}
