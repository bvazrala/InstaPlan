// Demo stand-ins for what the backend and the other members would supply.
// Everything the trip panel shows is derived from these plus what the logged-in user does in the UI.
import type { Message } from "@/lib/types";
import type { Extraction } from "@/lib/trip-model";
import { TRIP_CHAT } from "./demo-data";

/** Who is in each group chat. */
export const TRIP_MEMBERS: Record<string, string[]> = {
  crew: ["me", "maya", "alex", "sam", "jordan"],
};

/** Trip-related messages per group chat. The crew chat's first message triggers the trip offer. Jordan never speaks, so is not part of the plan. */
export const TRIP_THREADS: Record<string, Message[]> = {
  crew: [
    ...TRIP_CHAT,
    { id: "t6", from: "alex", kind: "text", text: "I can't do more than 5 hours of flying" },
    { id: "t7", from: "maya", kind: "text", text: "vegetarian here, fyi" },
  ],
};

/** What the group assistant (Muse) extracts from each message above. */
export const EXTRACTIONS: Record<string, Extraction[]> = {
  t1: [{ scope: "group", field: "destination", value: "New York City" }],
  t2: [
    { scope: "me", field: "from", value: "Austin" },
    { scope: "me", field: "mode", value: "Fly" },
  ],
  t3: [{ scope: "alex", field: "from", value: "Dallas" }],
  t4: [{ scope: "sam", field: "diet", value: "No seafood" }],
  t5: [{ scope: "group", field: "dates", value: "Dec 18 – 21" }],
  t6: [{ scope: "alex", field: "distance", value: "Up to 5 hours" }],
  t7: [{ scope: "maya", field: "diet", value: "Vegetarian" }],
};

/** Actions the other members have already taken in this trip. Real ones arrive over the WebSocket. */
export const OTHER_VOTES: Record<string, Record<string, "yes">> = {
  crew: { maya: "yes", alex: "yes" },
};
export const OTHER_EXPENSES_DONE: Record<string, string[]> = {
  crew: ["maya", "alex", "sam"],
};
export const OTHER_ACCEPTS: Record<string, string[]> = {
  crew: ["maya", "alex"],
};
export const OTHER_CHECKINS: Record<string, string[]> = {
  crew: ["maya", "alex"],
};
