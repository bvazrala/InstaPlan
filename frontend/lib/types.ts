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

export type TravelLeg = {
  id: string; origin: string; mode: "Flight" | "Drive"; hours: number | null; cost: number | null;
  lodgingAllocation?: number | null; subtotal?: number | null;
};

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
  cats: Record<Category, number | null>;
  /**
   * 1 = fairest. Computed on the server from private budgets.
   * The server never sends the underlying burden ratio: with similar costs per person,
   * that number would reveal the tightest budget in the group.
   */
  fairestRank: number;
  people: TravelLeg[];
  hue: number;
  currency?: string;
  groupTotal?: number | null;
  lodgingTotal?: number | null;
  maxTravelHours?: number | null;
  durationBasis?: "round_trip";
  priceCoverage?: string;
  feasibility?: "feasible" | "unverified" | "infeasible";
  pickEligible?: boolean;
  capacityAckRequired?: boolean;
  warnings?: string[];
  costScope?: "flights_and_lodging";
  listingUrl?: string | null;
  pricedAt?: string | null;
};

export type PersistedTrip = {
  id: string; chatId: string; stage: Stage; pickedOptionId: string | null;
  yesVotes: number; memberCount: number; checkinsDone: number;
};
export type PlanningInputs = {
  destinations: { name: string; airports: string[]; sourceFactIds?: string[] }[];
  checkin: string | null; checkout: string | null; origins: Record<string, string>;
};
export type Generation = {
  status: "idle" | "resolving" | "generating" | "needs_input" | "ready" | "failed";
  runId: string | null; message: string | null; missing: string[];
  inputs: PlanningInputs | null; partial: boolean; optionCount: number;
};

export type Stage = "idle" | "collecting" | "voting" | "confirmed" | "checkin" | "options" | "expenses" | "picked" | "finalize" | "settle";

export type SortKey = "cheapest" | "fastest" | "balanced" | "fairest";

/** Events the backend pushes over the chat WebSocket. `private.*` events are only ever sent to their owner. */
export type ServerEvent =
  | { type: "chat.ready" }
  | { type: "planner.updated"; tripId: string }
  | { type: "message.new"; message: ChatMessage }
  | { type: "trip.offer"; chatId: string }
  | { type: "trip.stage"; tripId: string; stage: Stage }
  | { type: "fact.updated"; tripId: string; fact: Fact }
  | { type: "options.ready"; tripId: string }
  | { type: "private.checkin"; tripId: string; message: Message }
  | { type: "error"; detail: string };

export type PlannerTopic = "Dining" | "Travel" | "Entertainment";
export type Venue = { fit: number | null; id: string; title: string; address: string | null; rating: number | null;
  priceLevel: string | null; url: string | null; provider: string; retrievedAt: string;
  evidence: string[]; warnings: string[]; pickEligible: boolean };
export type Planner = {
  tripId: string; title: string; topic: PlannerTopic; timezone: string; revision: number;
  approvalRevision: number; status: "collecting" | "approved" | "picked";
  template: { title: string; topic: PlannerTopic;
    when: { flexibility: Record<string, {label: string}[] | null>; agreed: {label: string; date: string | null} | null };
    where: { destination: {id: string; name: string; address: string | null; url: string | null} | null;
      destinationHint: string | null; searchArea: string | null; origins: Record<string, string> };
    preferences: Record<string, string[]>; hardConstraints: Record<string, string[]>;
    cluster: Record<string, string | string[]>; sources: Record<string, string> };
  attendance: Record<string, {status: "going" | "conditional" | "not_going"; condition: string | null; inferred: boolean}>;
  poll: {eligible: string[]; approvals: string[]; changes: string[]; required: number; threshold: number; ready: boolean};
  listening: "idle" | "queued" | "listening" | "failed"; missing: string[]; generation: Generation;
  recommendations: {kind: "travel"; options: Option[]} | {kind: "venues"; venues: Venue[]};
  pricedMembers: string[]; pickedId: string | null; provenance: Record<string, string | null>;
};
