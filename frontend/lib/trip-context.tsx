"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { EXTRACTIONS, OTHER_ACCEPTS, OTHER_CHECKINS, OTHER_EXPENSES_DONE, OTHER_VOTES, TRIP_MEMBERS, TRIP_THREADS } from "@/mocks/trip-demo";
import { deriveProfile, noEdits, type Edits, type GroupField, type PersonField, type Profile } from "./trip-model";
import type { SortKey, Stage } from "./types";

/** `split` includes the payer: their own share is part of the total, so nobody owes them for it. */
export type Expense = { id: string; what: string; payer: string; amount: number; split: string[] };

/** Everything about one trip. Each group chat has its own, so several plans can run at once. */
export type Trip = {
  stage: Stage;
  offerDismissed: boolean;
  sort: SortKey;
  pickedId: string | null;
  edits: Edits;
  /** Members who tapped "I'm in". */
  votes: Record<string, "yes">;
  /** Members who tapped "Not going". They stay out of the plan until they tap "I'm in" again. */
  optedOut: string[];
  /** Who has submitted their check-in. A count is all the group ever sees. */
  checkedIn: string[];
  /** The logged-in user's private answers. Never shared with the group. */
  mine: { budget: string; access: string[]; noGos: string };
  expenses: Expense[];
  /** Who has finished adding expenses. The final cost unlocks when every participant is in here. */
  expensesDone: string[];
  /** Who accepted the final plan. */
  accepts: string[];
  /** Plain-words change requests sent to the assistant. */
  requests: string[];
  paid: string[];
};

const blank = (chatId: string): Trip => ({
  stage: "idle",
  offerDismissed: false,
  sort: "balanced",
  pickedId: null,
  edits: noEdits(),
  votes: { ...OTHER_VOTES[chatId] },
  optedOut: [],
  checkedIn: [...(OTHER_CHECKINS[chatId] ?? [])],
  mine: { budget: "", access: [], noGos: "" },
  expenses: [],
  expensesDone: [...(OTHER_EXPENSES_DONE[chatId] ?? [])],
  accepts: [...(OTHER_ACCEPTS[chatId] ?? [])],
  requests: [],
  paid: [],
});

const ONLY_ME = ["me"];
const without = (arr: string[], id: string) => arr.filter((x) => x !== id);

type Ctx = {
  /** The chat whose trip the panel is showing. */
  activeChat: string;
  setActiveChat: (id: string) => void;
  tripOf: (chatId: string) => Trip;
  /** Everyone in the chat. */
  members: string[];
  /** Who is in the plan: spoke in the chat (or tapped "I'm in") and hasn't opted out. */
  participants: string[];
  inactive: { id: string; reason: string }[];
  profile: Profile;
  trip: Trip;
  update: (fn: (t: Trip) => Partial<Trip>) => void;
  stage: Stage;
  setStage: (s: Stage) => void;
  dismissOffer: () => void;
  offerDismissed: boolean;
  sort: SortKey;
  setSort: (s: SortKey) => void;
  pickedId: string | null;
  pick: (id: string | null) => void;
  /** "I'm in": joins the plan even if you haven't spoken, and undoes "Not going". */
  join: () => void;
  optOut: () => void;
  editField: (scope: "group" | string, field: GroupField | PersonField, value: string) => void;
  /** More than half of the participants must accept before the trip is final. */
  need: number;
  accepted: number;
  finalized: boolean;
  panelOpen: boolean;
  setPanelOpen: (b: boolean) => void;
};

const TripCtx = createContext<Ctx | null>(null);

export function TripProvider({ children }: { children: ReactNode }) {
  const [activeChat, setActiveChat] = useState("crew");
  const [trips, setTrips] = useState<Record<string, Trip>>(() => ({ crew: blank("crew") }));
  const [panelOpen, setPanelOpen] = useState(false);

  const tripOf = useCallback((id: string) => trips[id] ?? blank(id), [trips]);
  const trip = tripOf(activeChat);
  const members = TRIP_MEMBERS[activeChat] ?? ONLY_ME;

  const update = useCallback(
    (fn: (t: Trip) => Partial<Trip>) =>
      setTrips((all) => {
        const cur = all[activeChat] ?? blank(activeChat);
        return { ...all, [activeChat]: { ...cur, ...fn(cur) } };
      }),
    [activeChat],
  );

  const profile = useMemo(
    () => deriveProfile(TRIP_THREADS[activeChat] ?? [], EXTRACTIONS, trip.edits, members),
    [activeChat, trip.edits, members],
  );

  const spoke = new Set((TRIP_THREADS[activeChat] ?? []).map((m) => m.from));
  const participants = members.filter((id) => !trip.optedOut.includes(id) && (spoke.has(id) || trip.votes[id] === "yes"));
  const inactive = members
    .filter((id) => !participants.includes(id))
    .map((id) => ({ id, reason: trip.optedOut.includes(id) ? "Not going" : "Hasn't joined the chat about this" }));

  const need = Math.floor(participants.length / 2) + 1;
  const accepted = trip.accepts.filter((id) => participants.includes(id)).length;
  const finalized = participants.length > 0 && accepted >= need;

  const value: Ctx = {
    activeChat, setActiveChat, tripOf, members, participants, inactive, profile, trip, update,
    stage: trip.stage,
    setStage: (stage) => update(() => ({ stage })),
    offerDismissed: trip.offerDismissed,
    dismissOffer: () => update(() => ({ offerDismissed: true })),
    sort: trip.sort,
    setSort: (sort) => update(() => ({ sort })),
    pickedId: trip.pickedId,
    pick: (pickedId) => update(() => ({ pickedId })),
    join: () => update((t) => ({ votes: { ...t.votes, me: "yes" }, optedOut: without(t.optedOut, "me") })),
    optOut: () =>
      update((t) => {
        const { me: _me, ...votes } = t.votes;
        void _me;
        return {
          votes,
          optedOut: t.optedOut.includes("me") ? t.optedOut : [...t.optedOut, "me"],
          accepts: without(t.accepts, "me"),
          expensesDone: without(t.expensesDone, "me"),
          checkedIn: without(t.checkedIn, "me"),
        };
      }),
    // Your own preferences and the shared trip fields are editable. Other people's are not.
    editField: (scope, field, v) => {
      if (scope !== "group" && scope !== "me") return;
      update((t) => ({
        edits:
          scope === "group"
            ? { ...t.edits, group: { ...t.edits.group, [field]: v } }
            : { ...t.edits, people: { ...t.edits.people, me: { ...t.edits.people.me, [field]: v } } },
      }));
    },
    need, accepted, finalized,
    panelOpen, setPanelOpen,
  };
  return <TripCtx.Provider value={value}>{children}</TripCtx.Provider>;
}

export function useTrip() {
  const c = useContext(TripCtx);
  if (!c) throw new Error("useTrip must be used inside TripProvider");
  return c;
}
