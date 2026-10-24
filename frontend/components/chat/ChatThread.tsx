"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Camera, ChevronRight, Image as ImageIcon, Mic, Phone, Plus, Video } from "lucide-react";
import { MESSAGES, TRIP_CHAT, memberById } from "@/mocks/demo-data";
import type { Chat, Message } from "@/lib/types";
import { useTrip } from "@/lib/trip-context";
import { Avatar, GroupAvatar } from "./Avatar";
import TripChatCard from "@/components/trip/TripChatCard";
import MessageBubble from "./MessageBubble";

export default function ChatThread({ chat, onBack }: { chat: Chat; onBack: () => void }) {
  const { stage, setPanelOpen } = useTrip();
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState<Message[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const isCrew = chat.id === "crew";
  const base = isCrew ? [...MESSAGES, ...(stage === "idle" ? TRIP_CHAT.slice(0, 1) : TRIP_CHAT)] : [
    { id: "s1", from: chat.members[0], kind: "text", text: chat.sub } as Message,
  ];
  const messages = [...base, ...(isCrew ? sent : [])];

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages.length, stage]);

  const send = () => {
    const t = draft.trim();
    if (!t) return;
    setSent((s) => [...s, { id: `u${s.length}`, from: "me", kind: "text", text: t }]);
    setDraft("");
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-white md:rounded-3xl md:border md:border-line">
      <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line px-3 md:px-5">
        <button onClick={onBack} className="p-1 md:hidden" aria-label="Back"><ArrowLeft size={22} /></button>
        {chat.group ? <GroupAvatar ids={chat.members} size={40} /> : <Avatar id={chat.members[0]} size={40} />}
        <div className="min-w-0 flex-1 leading-tight">
          <p className="flex items-center gap-1 truncate text-[15px] font-semibold">{chat.name} <ChevronRight size={14} className="text-muted" /></p>
          <p className="text-xs text-muted">{chat.sub}</p>
        </div>
        <button className="flex h-9 w-9 items-center justify-center rounded-full md:border md:border-line" aria-label="Call"><Phone size={18} /></button>
        <button className="flex h-9 w-9 items-center justify-center rounded-full md:border md:border-line" aria-label="Video"><Video size={18} /></button>
      </header>

      <div className="no-scrollbar flex-1 space-y-1 overflow-y-auto px-4 py-4 md:px-8">
        <p className="pb-3 text-center text-[11px] text-muted">Today 9:27 AM</p>
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          const first = prev?.from !== m.from;
          const mine = m.from === "me";
          const next = messages[i + 1];
          const last = next?.from !== m.from;
          return (
            <div key={m.id} className={`animate-in-fade ${first ? "pt-3" : ""}`}>
              {first && !mine && chat.group && <p className="mb-1 ml-10 text-[11px] text-muted">{memberById(m.from).name}</p>}
              <div className={`flex items-end gap-2 ${mine ? "justify-end" : ""}`}>
                {!mine && (
                  <span className="w-7 shrink-0">{last && chat.group ? <Avatar id={m.from} size={28} /> : null}</span>
                )}
                <MessageBubble m={m} />
              </div>
            </div>
          );
        })}
        {isCrew && <TripChatCard />}
        {isCrew && sent.length > 0 && <p className="pr-1 text-right text-[11px] text-muted">Seen by everyone</p>}
        <div ref={endRef} />
      </div>

      <div className="shrink-0 border-t border-line p-3 md:p-4">
        <div className="flex items-center gap-2 rounded-full bg-surface py-1.5 pl-1.5 pr-2">
          <button className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#3b9cf5] text-white" aria-label="Camera"><Camera size={18} /></button>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Message..."
            className="min-w-0 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-muted"
          />
          {draft ? (
            <button onClick={send} className="px-3 text-sm font-semibold text-brand">Send</button>
          ) : (
            <>
              <Mic size={20} className="mx-1 md:hidden" />
              <ImageIcon size={20} className="mx-1 md:hidden" />
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-[10px] font-bold">GIF</span>
              <button onClick={() => setPanelOpen(true)} className="flex h-8 w-8 items-center justify-center rounded-full bg-white" aria-label="More options"><Plus size={18} /></button>
              <span className="hidden h-8 w-8 items-center justify-center rounded-full bg-white md:flex"><Mic size={16} /></span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
