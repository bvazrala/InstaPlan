// Real-time client: one WebSocket per open chat.
// The server sends group events to every member of the chat and `private.*` events only to their owner.
// The token goes in the first message, not the URL, so it never lands in server logs.
import { API_URL } from "./api";
import { getAccessToken } from "./supabase";
import type { ServerEvent } from "./types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? API_URL.replace(/^http/, "ws");

export async function connectChat(chatId: string, onEvent: (e: ServerEvent) => void, onClose?: () => void) {
  const token = await getAccessToken();
  if (!token) throw new Error("Sign in to connect to chat");
  const ws = new WebSocket(`${WS_URL}/ws/chats/${chatId}`);
  await new Promise<void>((resolve, reject) => {
    let ready = false;
    const timeout = setTimeout(() => { ws.close(); reject(new Error("Chat connection timed out")); }, 12000);
    ws.addEventListener("open", () => ws.send(JSON.stringify({ type: "auth", token })));
    ws.addEventListener("message", (msg) => {
      const event = JSON.parse(msg.data) as ServerEvent;
      if (event.type === "chat.ready") {
        ready = true;
        clearTimeout(timeout);
        resolve();
      } else onEvent(event);
    });
    ws.addEventListener("close", () => {
      clearTimeout(timeout);
      if (ready) onClose?.();
      else reject(new Error("Chat connection closed before authentication"));
    });
  });

  return {
    sendMessage: (text: string) => ws.send(JSON.stringify({ type: "message.send", text })),
    close: () => ws.close(),
  };
}
