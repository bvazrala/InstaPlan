// Client-side re-sorting of options the server already priced (R13: no new API calls).
import type { Option, SortKey } from "./types";

export const personTotal = (o: Option, memberId: string) => {
  const leg = o.people.find((x) => x.id === memberId);
  return (leg?.cost ?? 0) + o.lodgingShare + o.daily * o.nights;
};

export const groupTotal = (o: Option) => o.people.reduce((sum, leg) => sum + personTotal(o, leg.id), 0);

export const perPerson = (o: Option) => groupTotal(o) / Math.max(1, o.people.length);

/** Longest travel time in the group, so nobody spends a day getting there. */
export const maxHours = (o: Option) => Math.max(...o.people.map((x) => x.hours));

/** Balanced uses weight w for cost and (1 − w) for time, each normalized 0–1 across the current options. */
export function sortOptions(opts: Option[], key: SortKey, w = 0.5): Option[] {
  const cost = opts.map(groupTotal);
  const time = opts.map(maxHours);
  const norm = (v: number, a: number[]) => {
    const lo = Math.min(...a), hi = Math.max(...a);
    return hi === lo ? 0 : (v - lo) / (hi - lo);
  };
  const score = (o: Option, i: number) =>
    key === "cheapest" ? cost[i]
    : key === "fastest" ? time[i]
    : key === "fairest" ? o.fairestRank
    : w * norm(cost[i], cost) + (1 - w) * norm(time[i], time);
  return opts.map((o, i) => ({ o, s: score(o, i) })).sort((a, b) => a.s - b.s).map((x) => x.o);
}
