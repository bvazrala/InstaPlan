// Shared frontend types. Field names match the backend's camelCase JSON (see docs/api-contract.md).

export type Member = { id: string; name: string; handle: string; hue: number; origin: string | null };

export type Chat = { id: string; name: string; sub: string; unread?: number; members: string[]; group?: boolean };

export type Message =
  | { id: string; from: string; kind: "text"; text: string }
  | { id: string; from: string; kind: "image"; caption?: string };

/** Stored group-chat message returned by FastAPI and sent in message.new events. */
export type ChatMessage = { id: string; from: string; kind: "text"; text: string; sentAt: string };

export type Fact = { id: string; field: string; value: string; by: string; src: string; required?: boolean };

export const CATEGORIES = ["Destination", "Lodging", "Food", "Activities", "Travel"] as const;
export type Category = (typeof CATEGORIES)[number];

export type TravelLeg = { id: string; origin: string; mode: "Flight" | "Drive"; hours: number; cost: number };

export type Option = {
  id: string;
  title: string;
  place: string;
  dates: string;
  nights: number;
  lodging: string;
  lodgingShare: number;
  daily: number;
  fit: number;
  certainty: string;
  cats: Record<Category, number>;
  /**
   * 1 = fairest. Computed on the server from private budgets.
   * The server never sends the underlying burden ratio: with similar costs per person,
   * that number would reveal the tightest budget in the group.
   */
  fairestRank: number;
  people: TravelLeg[];
  hue: number;
};

export type Stage = "idle" | "collecting" | "voting" | "checkin" | "options" | "expenses" | "picked" | "finalize" | "settle";

export type SortKey = "cheapest" | "fastest" | "balanced" | "fairest";

/** Events the backend pushes over the chat WebSocket. `private.*` events are only ever sent to their owner. */
export type ServerEvent =
  | { type: "chat.ready" }
  | { type: "message.new"; message: ChatMessage }
  | { type: "trip.offer"; chatId: string }
  | { type: "trip.stage"; tripId: string; stage: Stage }
  | { type: "fact.updated"; tripId: string; fact: Fact }
  | { type: "options.ready"; tripId: string }
  | { type: "private.checkin"; tripId: string; message: Message }
  | { type: "error"; detail: string };
