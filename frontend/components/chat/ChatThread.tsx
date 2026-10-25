"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, CornerUpLeft, Image as ImageIcon, MapPin, Mic, Phone, Smile, Sticker, Video, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { connectChat } from "@/lib/socket";
import type { Chat, ChatMessage, Member, Message } from "@/lib/types";
import { useTrip } from "@/lib/trip-context";
import { Avatar, ChatAvatar } from "./Avatar";
import TripChatCard from "@/components/trip/TripChatCard";
import MessageBubble, { type BubblePos } from "./MessageBubble";
import { STAGE_LABEL } from "./chat-meta";

const iconBtn = "flex size-9 items-center justify-center rounded-full text-foreground transition hover:bg-surface";

function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]) {
  const byId = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) byId.set(message.id, message);
  return [...byId.values()].sort((a, b) => a.sentAt.localeCompare(b.sentAt));
}

export default function ChatThread({ chat, me, members, onLatest, onBack }: {
  chat: Chat; me: string; members: Record<string, Member>;
  onLatest: (chatId: string, message: ChatMessage) => void; onBack: () => void;
}) {
  const { stage, setStage, panelOpen, setPanelOpen } = useTrip();
  const [draft, setDraft] = useState("");
  const [stored, setStored] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [replyTo, setReplyTo] = useState<{ id: string; who: string; text: string } | null>(null);
  const [quotes, setQuotes] = useState<Record<string, { who: string; text: string }>>({});
  const [reacted, setReacted] = useState<Record<string, boolean>>({});
  const endRef = useRef<HTMLDivElement>(null);

  const messages: Message[] = stored.map((message) => ({ id: message.id, from: message.from === me ? "me" : message.from, kind: "text", text: message.text }));
  const seps: Record<number, string> = stored.length ? { 0: new Date(stored[0].sentAt).toLocaleDateString(undefined, { month: "short", day: "numeric" }) } : {};
  const lastMine = messages.at(-1)?.from === "me";

  useEffect(() => {
    let cancelled = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let connection: Awaited<ReturnType<typeof connectChat>> | undefined;
    const refresh = async () => {
      try {
        const list = await apiFetch<ChatMessage[]>(`/chats/${chat.id}/messages`);
        if (cancelled) return;
        setStored((current) => mergeMessages(current, list));
        if (list.length) onLatest(chat.id, list.at(-1)!);
        setError(null);
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load messages");
      }
    };
    const subscribe = async () => {
      try {
        connection = await connectChat(chat.id, (event) => {
          if (event.type !== "message.new" || cancelled) return;
          setStored((current) => mergeMessages(current, [event.message]));
          onLatest(chat.id, event.message);
        }, () => {
          if (!cancelled) retry = setTimeout(() => void subscribe(), 1500);
        });
        if (cancelled) connection.close();
        else await refresh();
      } catch {
        if (!cancelled) retry = setTimeout(() => void subscribe(), 1500);
      }
    };
    void refresh();
    void subscribe();
    return () => { cancelled = true; if (retry) clearTimeout(retry); connection?.close(); };
  }, [chat.id, onLatest]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [chat.id, stored.length, stage]);

  const send = async () => {
    const t = draft.trim();
    if (!t) return;
    try {
      const message = await apiFetch<ChatMessage>(`/chats/${chat.id}/messages`, { method: "POST", body: JSON.stringify({ text: t }) });
      setStored((current) => mergeMessages(current, [message]));
      onLatest(chat.id, message);
      if (replyTo) setQuotes((q) => ({ ...q, [message.id]: { who: replyTo.who, text: replyTo.text } }));
      setReplyTo(null);
      setDraft("");
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Message could not be sent");
    }
  };
  const reply = (m: Message) => setReplyTo({ id: m.id, who: m.from === "me" ? "yourself" : members[m.from]?.name ?? "Member", text: m.kind === "image" ? "Photo" : m.text });
  const react = (id: string) => setReacted((r) => ({ ...r, [id]: !r[id] }));

  const subtitle = chat.sub;

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <header className="flex h-[68px] shrink-0 items-center gap-3 border-b border-line px-3 md:px-5">
        <button onClick={onBack} className={`${iconBtn} md:hidden`} aria-label="Back"><ArrowLeft size={22} /></button>
        <ChatAvatar chat={chat} size={40} members={members} />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate text-[15px] font-semibold">{chat.name}</p>
          <p className="flex items-center gap-1 truncate text-xs text-muted">
            {subtitle}
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
                  {showName && <p className="mb-0.5 ml-10 text-[11px] text-muted">{members[m.from]?.name ?? "Member"}</p>}
                  <div className={`flex items-end gap-2 ${mine ? "justify-end" : ""}`}>
                    {!mine && <span className="w-7 shrink-0">{!sameAsNext && chat.group ? <Avatar id={m.from} size={28} members={members} /> : null}</span>}
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
            onKeyDown={(e) => { if (e.key === "Enter") void send(); }}
            placeholder="Message…"
            className="min-w-0 flex-1 bg-transparent px-2 py-2.5 text-[15px] outline-none placeholder:text-muted "
          />
          {draft.trim() ? (
            <button onClick={() => void send()} className="px-3 text-sm font-semibold text-brand">Send</button>
          ) : (
            <>
              <button className={iconBtn} aria-label="Voice note"><Mic size={21} strokeWidth={1.75} /></button>
              <button className={iconBtn} aria-label="Photo"><ImageIcon size={21} strokeWidth={1.75} /></button>
              <button className={`${iconBtn} hidden md:flex`} aria-label="Sticker"><Sticker size={21} strokeWidth={1.75} /></button>
            </>
          )}
        </div>
        {error && <p role="alert" className="mt-1 px-3 text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}
