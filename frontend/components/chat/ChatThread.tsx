"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, CornerUpLeft, Image as ImageIcon, MapPin, Mic, Phone, Smile, Sticker, Video, X } from "lucide-react";
import { memberById } from "@/mocks/demo-data";
import type { Chat, Message } from "@/lib/types";
import { useTrip } from "@/lib/trip-context";
import { Avatar, ChatAvatar } from "./Avatar";
import TripChatCard from "@/components/trip/TripChatCard";
import MessageBubble, { type BubblePos } from "./MessageBubble";
import { CHAT_META, STAGE_LABEL, baseMessages, separators } from "./chat-meta";

const iconBtn = "flex size-9 items-center justify-center rounded-full text-foreground transition hover:bg-surface";

export default function ChatThread({ chat, onBack }: { chat: Chat; onBack: () => void }) {
  const { stage, setStage, panelOpen, setPanelOpen } = useTrip();
  const [draft, setDraft] = useState("");
  const [sentBy, setSentBy] = useState<Record<string, Message[]>>({});
  const [replyTo, setReplyTo] = useState<{ id: string; who: string; text: string } | null>(null);
  const [quotes, setQuotes] = useState<Record<string, { who: string; text: string }>>({});
  const [reacted, setReacted] = useState<Record<string, boolean>>({});
  const endRef = useRef<HTMLDivElement>(null);

  const sent = sentBy[chat.id] ?? [];
  const messages = [...baseMessages(chat.id, stage), ...sent];
  const seps = separators(chat.id);
  const lastMine = messages.at(-1)?.from === "me";

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [chat.id, messages.length, sent.length, stage]);

  const send = () => {
    const t = draft.trim();
    if (!t) return;
    const id = `u-${chat.id}-${sent.length}`;
    setSentBy((s) => ({ ...s, [chat.id]: [...(s[chat.id] ?? []), { id, from: "me", kind: "text", text: t }] }));
    if (replyTo) setQuotes((q) => ({ ...q, [id]: { who: replyTo.who, text: replyTo.text } }));
    setReplyTo(null);
    setDraft("");
  };
  const reply = (m: Message) => setReplyTo({ id: m.id, who: m.from === "me" ? "yourself" : memberById(m.from).name, text: m.kind === "image" ? "Photo" : m.text });
  const react = (id: string) => setReacted((r) => ({ ...r, [id]: !r[id] }));

  const meta = CHAT_META[chat.id];
  const subtitle = meta?.presence ?? chat.sub;
  const online = !!meta?.online && !chat.group;

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <header className="flex h-[68px] shrink-0 items-center gap-3 border-b border-line px-3 md:px-5">
        <button onClick={onBack} className={`${iconBtn} md:hidden`} aria-label="Back"><ArrowLeft size={22} /></button>
        <ChatAvatar chat={chat} size={40} online={online} />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate text-[15px] font-semibold">{chat.name}</p>
          <p className={`flex items-center gap-1 truncate text-xs ${online ? "text-emerald-600" : "text-muted"}`}>
            {online ? "Active now" : subtitle}
          </p>
        </div>
        <button className={iconBtn} aria-label="Voice call"><Phone size={20} strokeWidth={1.75} /></button>
        <button className={iconBtn} aria-label="Video call"><Video size={21} strokeWidth={1.75} /></button>
        {chat.group && (
          <button
            onClick={() => setPanelOpen(!panelOpen)}
            aria-pressed={panelOpen}
            className={`flex h-9 items-center gap-1.5 rounded-full px-3.5 text-[13px] font-semibold transition ${panelOpen ? "bg-brand text-white" : "bg-surface text-foreground hover:bg-neutral-100"}`}
          >
            <MapPin size={15} /> {stage === "idle" ? "Plan trip" : "Trip"}
            {stage !== "idle" && <span className="hidden font-normal opacity-80 sm:inline">· {STAGE_LABEL[stage]}</span>}
          </button>
        )}
      </header>


      <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-8">
        <div className="space-y-0.5">
            {messages.map((m, i) => {
              const prev = messages[i - 1];
              const next = messages[i + 1];
              const mine = m.from === "me";
              const sameAsPrev = !!prev && prev.from === m.from && !seps[i];
              const sameAsNext = !!next && next.from === m.from && !seps[i + 1];
              const pos: BubblePos = m.kind === "image" ? "single" : sameAsPrev ? (sameAsNext ? "middle" : "last") : sameAsNext ? "first" : "single";
              const showName = !mine && chat.group && !sameAsPrev;
              return (
                <div key={m.id} className="animate-in-fade">
                  {seps[i] && <p className="pb-3 pt-4 text-center text-xs font-medium text-muted">{seps[i]}</p>}
                  {!sameAsPrev && i > 0 && !seps[i] && <div className="h-2.5" />}
                  {showName && <p className="mb-0.5 ml-10 text-[11px] text-muted">{memberById(m.from).name}</p>}
                  <div className={`flex items-end gap-2 ${mine ? "justify-end" : ""}`}>
                    {!mine && <span className="w-7 shrink-0">{!sameAsNext && chat.group ? <Avatar id={m.from} size={28} /> : null}</span>}
                    <div className={`flex min-w-0 flex-1 flex-col ${mine ? "items-end" : "items-start"}`}>
                      {quotes[m.id] && (
                        <p className="mb-0.5 max-w-[68%] truncate rounded-xl bg-surface px-3 py-1 text-xs text-muted">
                          Replying to {quotes[m.id].who}: {quotes[m.id].text}
                        </p>
                      )}
                      <MessageBubble m={m} pos={pos} reacted={!!reacted[m.id]} onReact={() => react(m.id)} onReply={() => reply(m)} />
                    </div>
                  </div>
                </div>
              );
            })}
            {chat.group && <TripChatCard />}
            {lastMine && <p className="pr-1 pt-1.5 text-right text-[11px] text-muted">Seen</p>}
        </div>
        <div ref={endRef} />
      </div>

      <div className="shrink-0 px-3 pb-3 pt-1 md:px-5 md:pb-5 [padding-bottom:max(0.75rem,env(safe-area-inset-bottom))]">
        {chat.group && stage === "idle" && (
          <div className="no-scrollbar -mx-1 mb-2 flex gap-2 overflow-x-auto px-1">
            <button
              onClick={() => { setStage("collecting"); setPanelOpen(true); }}
              className="flex shrink-0 items-center gap-1.5 rounded-full border border-line px-3.5 py-1.5 text-[13px] font-semibold transition hover:bg-surface"
            >
              <MapPin size={14} className="text-brand" /> Plan a trip
            </button>
          </div>
        )}
        {replyTo && (
          <div className="mb-2 flex items-center gap-2 rounded-xl bg-surface px-3 py-2 text-xs">
            <CornerUpLeft size={14} className="shrink-0 text-muted" />
            <p className="min-w-0 flex-1 truncate text-muted">Replying to <span className="font-semibold text-foreground">{replyTo.who}</span>: {replyTo.text}</p>
            <button onClick={() => setReplyTo(null)} aria-label="Cancel reply"><X size={14} /></button>
          </div>
        )}
        <div className="flex min-h-11 items-center gap-1 rounded-full border border-line bg-white pl-3 pr-1.5 transition focus-within:border-neutral-300">
          <Smile size={22} strokeWidth={1.75} className="text-foreground" />
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Message…"
            className="min-w-0 flex-1 bg-transparent px-2 py-2.5 text-[15px] outline-none placeholder:text-muted "
          />
          {draft.trim() ? (
            <button onClick={send} className="px-3 text-sm font-semibold text-brand">Send</button>
          ) : (
            <>
              <button className={iconBtn} aria-label="Voice note"><Mic size={21} strokeWidth={1.75} /></button>
              <button className={iconBtn} aria-label="Photo"><ImageIcon size={21} strokeWidth={1.75} /></button>
              <button className={`${iconBtn} hidden md:flex`} aria-label="Sticker"><Sticker size={21} strokeWidth={1.75} /></button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
