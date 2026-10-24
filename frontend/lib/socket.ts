// Real-time client: one WebSocket per open chat.
// The server sends group events to every member of the chat and `private.*` events only to their owner.
// The token goes in the first message, not the URL, so it never lands in server logs.
import { API_URL } from "./api";
import { getAccessToken } from "./supabase";
import type { ServerEvent } from "./types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? API_URL.replace(/^http/, "ws");

export async function connectChat(chatId: string, onEvent: (e: ServerEvent) => void) {
  const ws = new WebSocket(`${WS_URL}/ws/chats/${chatId}`);
  const token = await getAccessToken();

  ws.addEventListener("open", () => ws.send(JSON.stringify({ type: "auth", token })));
  ws.addEventListener("message", (msg) => onEvent(JSON.parse(msg.data) as ServerEvent));

  return {
    sendMessage: (text: string) => ws.send(JSON.stringify({ type: "message.send", text })),
    close: () => ws.close(),
  };
}
