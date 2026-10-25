import type { Option, Generation, PersistedTrip } from "@/lib/types";
export const option = (overrides: Partial<Option> = {}): Option => ({
  id: "a", title: "Shared stay A", place: "New York City", dates: "2030-11-05..2030-11-09", nights: 4,
  lodging: "Apartment", lodgingShare: 33.336666, daily: 0, fit: 50, certainty: "0 of 3 weighed in",
  cats: { Destination: 50, Lodging: 50, Travel: 50, Food: null, Activities: null }, fairestRank: 1, hue: 260,
  currency: "USD", groupTotal: 700.01, lodgingTotal: 100.01, maxTravelHours: 6, durationBasis: "round_trip",
  priceCoverage: "quoted_with_taxes", feasibility: "unverified", pickEligible: true, capacityAckRequired: true,
  people: [
    { id: "alice", origin: "AUS", mode: "Flight", cost: 100, hours: 2, lodgingAllocation: 33.34, subtotal: 133.34 },
    { id: "bob", origin: "BOS", mode: "Flight", cost: 200, hours: 4, lodgingAllocation: 33.34, subtotal: 233.34 },
    { id: "cara", origin: "LAX", mode: "Flight", cost: 300, hours: 6, lodgingAllocation: 33.33, subtotal: 333.33 },
  ], pricedAt: "2026-10-25T12:00:00Z", ...overrides,
});
export const trip: PersistedTrip = { id: "trip-a", chatId: "chat-a", stage: "options", pickedOptionId: null, yesVotes: 3, memberCount: 3, checkinsDone: 2 };
export const status: Generation = { status: "ready", runId: "run", message: null, missing: [], inputs: null, partial: false, optionCount: 1 };
