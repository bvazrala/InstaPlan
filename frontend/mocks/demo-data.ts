// Demo data for the UI while the backend is being built.
// Each export is replaced by an API call or WebSocket event as features land (see README → "Wiring real data").
import type { Chat, Fact, Member, Message, Option, TravelLeg } from "@/lib/types";

export const ME: Member = { id: "me", name: "You", handle: "you", hue: 262, origin: "AUS" };

export const MEMBERS: Member[] = [
  ME,
  { id: "maya", name: "Maya", handle: "maya.k", hue: 24, origin: "AUS" },
  { id: "alex", name: "Alex", handle: "alexr", hue: 200, origin: "DFW" },
  { id: "sam", name: "Sam", handle: "sam.t", hue: 330, origin: "AUS" },
  { id: "jordan", name: "Jordan", handle: "jordan.p", hue: 150, origin: "HOU" },
];

export const memberById = (id: string) => MEMBERS.find((m) => m.id === id) ?? ME;

export const CHATS: Chat[] = [
  { id: "crew", name: "weekend crew ☕", sub: "4 members", unread: 2, members: ["maya", "alex"], group: true },
  { id: "maya", name: "Maya", sub: "Coffee and a little wandering?", members: ["maya"] },
  { id: "alex", name: "Alex", sub: "Found our spot 👀", members: ["alex"] },
  { id: "sam", name: "Sam", sub: "I'm in! 11:30 at Juniper?", members: ["sam"] },
];

export const MESSAGES: Message[] = [
  { id: "m1", from: "maya", kind: "text", text: "Okay, Saturday plans? Coffee and a little wandering? ☕" },
  { id: "m2", from: "me", kind: "text", text: "Yes! I'm free after 11 🙌\nLet's make a day of it" },
  { id: "m3", from: "alex", kind: "image" },
  { id: "m4", from: "alex", kind: "text", text: "Found our spot 👀" },
  { id: "m5", from: "sam", kind: "text", text: "I'm in! 11:30 at Juniper?" },
  { id: "m6", from: "me", kind: "text", text: "11:30 it is! See you there 💜" },
];

/** Messages that arrive once a trip session is open (drives the live trip card demo). */
export const TRIP_CHAT: Message[] = [
  { id: "t1", from: "maya", kind: "text", text: "we should do a trip over winter break, maybe NYC?" },
  { id: "t2", from: "me", kind: "text", text: "flying from Austin" },
  { id: "t3", from: "alex", kind: "text", text: "Dallas here" },
  { id: "t4", from: "sam", kind: "text", text: "no seafood for me pls" },
  { id: "t5", from: "maya", kind: "text", text: "Dec 18 to 21 works" },
];

export const FACTS: Fact[] = [
  { id: "f1", field: "Destination", value: "New York City", by: "maya", src: "t1", required: true },
  { id: "f2", field: "Dates", value: "Dec 18 – 21 · 3 nights", by: "maya", src: "t5", required: true },
  { id: "f3", field: "From", value: "Austin ×3, Dallas ×1", by: "me", src: "t2", required: true },
  { id: "f4", field: "Food", value: "No seafood", by: "sam", src: "t4" },
];

export const MISSING_FIELDS = [{ field: "Travel mode", required: true }];

const leg = (id: string, origin: string, mode: TravelLeg["mode"], hours: number, cost: number): TravelLeg => ({
  id, origin, mode, hours, cost,
});

export const OPTIONS: Option[] = [
  {
    id: "o1", title: "Lower East Side loft", place: "New York, NY", dates: "Dec 18 – 21", nights: 3,
    lodging: "LES 3BR rental", lodgingShare: 215, daily: 95, fit: 86, certainty: "4 of 4 weighed in",
    cats: { Destination: 92, Lodging: 84, Food: 88, Activities: 90, Travel: 62 }, fairestRank: 3,
    people: [leg("me", "AUS", "Flight", 4.5, 318), leg("maya", "AUS", "Flight", 4.5, 318), leg("alex", "DFW", "Flight", 3.9, 274), leg("sam", "AUS", "Flight", 4.5, 318)],
    hue: 262,
  },
  {
    id: "o2", title: "Midtown hotel", place: "New York, NY", dates: "Dec 18 – 21", nights: 3,
    lodging: "2 rooms near Times Sq", lodgingShare: 290, daily: 105, fit: 71, certainty: "4 of 4 weighed in",
    cats: { Destination: 92, Lodging: 58, Food: 80, Activities: 84, Travel: 62 }, fairestRank: 4,
    people: [leg("me", "AUS", "Flight", 4.5, 318), leg("maya", "AUS", "Flight", 4.5, 318), leg("alex", "DFW", "Flight", 3.9, 274), leg("sam", "AUS", "Flight", 4.5, 318)],
    hue: 210,
  },
  {
    id: "o3", title: "Brooklyn brownstone", place: "Brooklyn, NY", dates: "Dec 19 – 22", nights: 3,
    lodging: "Williamsburg 3BR", lodgingShare: 185, daily: 85, fit: 64, certainty: "3 of 4 weighed in",
    cats: { Destination: 78, Lodging: 74, Food: 70, Activities: 55, Travel: 58 }, fairestRank: 2,
    people: [leg("me", "AUS", "Flight", 4.7, 296), leg("maya", "AUS", "Flight", 4.7, 296), leg("alex", "DFW", "Flight", 4.1, 252), leg("sam", "AUS", "Flight", 4.7, 296)],
    hue: 24,
  },
  {
    id: "o4", title: "Philly road trip", place: "Philadelphia, PA", dates: "Dec 18 – 21", nights: 3,
    lodging: "Old City 3BR", lodgingShare: 140, daily: 70, fit: 38, certainty: "2 of 4 weighed in",
    cats: { Destination: 40, Lodging: 66, Food: 52, Activities: 34, Travel: 22 }, fairestRank: 1,
    people: [leg("me", "AUS", "Drive", 23, 210), leg("maya", "AUS", "Drive", 23, 210), leg("alex", "DFW", "Drive", 21, 190), leg("sam", "AUS", "Drive", 23, 210)],
    hue: 340,
  },
];
