// Presentation-only chat data (presence, timestamps, direct-message history) that the demo mocks don't carry.
// Replaced by `sentAt` / presence from the API once the chat is wired (see docs/api-contract.md).
import { MESSAGES, memberById } from "@/mocks/demo-data";
import { TRIP_THREADS } from "@/mocks/trip-demo";
import type { Chat, Message, Stage } from "@/lib/types";

type Meta = { time: string; online?: boolean; presence: string };

export const CHAT_META: Record<string, Meta> = {
  crew: { time: "9m", online: true, presence: "You, Maya, Alex, Sam, Jordan" },
  maya: { time: "32m", online: true, presence: "Active now" },
  alex: { time: "1h", online: true, presence: "Active now" },
  sam: { time: "2h", presence: "Active 12m ago" },
};

/** Chats that start unread. Opening a chat marks it read (the server will own this once the chat is wired). */
export const INITIAL_UNREAD = ["crew", "sam"];

const DM_THREADS: Record<string, Message[]> = {
  maya: [
    { id: "dm-m1", from: "me", kind: "text", text: "Are we still on for Saturday?" },
    { id: "dm-m2", from: "maya", kind: "text", text: "Definitely. I'll bring the good camera." },
    { id: "dm-m3", from: "maya", kind: "text", text: "Coffee and a little wandering?" },
  ],
  alex: [
    { id: "dm-a1", from: "me", kind: "text", text: "Where should we meet?" },
    { id: "dm-a2", from: "alex", kind: "image" },
    { id: "dm-a3", from: "alex", kind: "text", text: "Found our spot 👀" },
  ],
  sam: [
    { id: "dm-s1", from: "me", kind: "text", text: "You coming Saturday?" },
    { id: "dm-s2", from: "sam", kind: "text", text: "I'm in! 11:30 at Juniper?" },
  ],
};

export function baseMessages(chatId: string, stage: Stage): Message[] {
  if (chatId === "crew") return [...MESSAGES, ...(stage === "idle" ? TRIP_THREADS.crew.slice(0, 1) : TRIP_THREADS.crew)];
  return DM_THREADS[chatId] ?? [];
}

/** Time labels shown above a message, keyed by its index in the thread. */
export function separators(chatId: string): Record<number, string> {
  return chatId === "crew" ? { 0: "Today 9:02 AM", [MESSAGES.length]: "9:27 AM" } : { 0: "Today 8:40 AM" };
}

export function previewText(chat: Chat, stage: Stage): string {
  const last = baseMessages(chat.id, stage).at(-1);
  if (!last) return chat.sub;
  const body = last.kind === "image" ? "Sent a photo" : last.text;
  if (last.from === "me") return `You: ${body}`;
  return chat.group ? `${memberById(last.from).name}: ${body}` : body;
}

export const STAGE_LABEL: Record<Exclude<Stage, "idle">, string> = {
  collecting: "Collecting details",
  voting: "Voting",
  checkin: "Private check-in",
  options: "Comparing options",
  expenses: "Adding expenses",
  picked: "Final cost",
  finalize: "Finalizing",
  settle: "Payments",
};
