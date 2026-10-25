"use client";

import { useState } from "react";
import { MapPin, Search, SquarePen } from "lucide-react";
import type { Chat } from "@/lib/types";
import { useTrip } from "@/lib/trip-context";
import { ChatAvatar } from "./Avatar";
import { Logo } from "./NavRail";
import { CHAT_META, STAGE_LABEL, previewText } from "./chat-meta";

const TABS = [
  { id: "all", label: "All" },
  { id: "groups", label: "Groups" },
  { id: "direct", label: "Direct" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export default function ChatList({ chats, activeId, unreadIds, onSelect }: { chats: Chat[]; activeId: string; unreadIds: string[]; onSelect: (id: string) => void }) {
  const { tripOf } = useTrip();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<Tab>("all");

  const q = query.trim().toLowerCase();
  const visible = chats.filter((c) => {
    if (q && !c.name.toLowerCase().includes(q)) return false;
    if (tab === "groups") return !!c.group;
    if (tab === "direct") return !c.group;
    return true;
  });

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center justify-between px-4 pb-1 pt-4 md:px-5 md:pt-5">
        <div className="flex items-center gap-2.5">
          <span className="md:hidden"><Logo size={32} /></span>
          <h1 className="text-[22px] font-bold tracking-tight">Messages</h1>
        </div>
        <button aria-label="New message" className="flex size-9 items-center justify-center rounded-full text-foreground transition hover:bg-surface"><SquarePen size={21} strokeWidth={1.75} /></button>
      </div>

      <label className="mx-4 mt-2 flex h-10 items-center gap-2.5 rounded-xl bg-surface px-3 text-muted md:mx-5">
        <Search size={16} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted"
          placeholder="Search"
        />
      </label>

      <div role="tablist" className="mt-3 flex gap-1.5 px-4 pb-2 md:px-5">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition ${tab === t.id ? "bg-foreground text-white" : "bg-surface text-foreground hover:bg-neutral-100"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <ul className="no-scrollbar flex-1 overflow-y-auto pb-2">
        {visible.map((c) => {
          const isActive = c.id === activeId;
          const stage = tripOf(c.id).stage;
          const unread = unreadIds.includes(c.id);
          const tripTag = !!c.group && stage !== "idle";
          return (
            <li key={c.id}>
              <button
                onClick={() => onSelect(c.id)}
                className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition md:px-5 ${isActive ? "bg-surface" : "hover:bg-surface/70"}`}
              >
                <ChatAvatar chat={c} size={52} online={!!CHAT_META[c.id]?.online && !c.group} />
                <span className="min-w-0 flex-1">
                  <span className={`block truncate text-[15px] ${unread ? "font-semibold" : "font-medium"}`}>{c.name}</span>
                  <span className={`flex items-center gap-1 text-[13px] ${unread ? "font-semibold text-foreground" : "text-muted"}`}>
                    {tripTag && (
                      <span className="flex shrink-0 items-center gap-1 rounded-full bg-violet-50 px-1.5 py-0.5 text-[11px] font-semibold text-brand">
                        <MapPin size={10} /> {STAGE_LABEL[stage as Exclude<typeof stage, "idle">]}
                      </span>
                    )}
                    <span className="truncate">{previewText(c, stage)}</span>
                    <span className="shrink-0 font-normal text-muted">· {CHAT_META[c.id]?.time}</span>
                  </span>
                </span>
                {unread && <span className="size-2.5 shrink-0 rounded-full bg-brand" aria-label="Unread" />}
              </button>
            </li>
          );
        })}
        {visible.length === 0 && <li className="px-5 py-10 text-center text-sm text-muted">No chats match “{query}”.</li>}
      </ul>
    </div>
  );
}
