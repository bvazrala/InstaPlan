// Local sorting of already-priced results; no network calls and no private budget values.
import type { Option, SortKey } from "./types";
const cents = (n: number) => Math.round(n * 100);
export const personTotal = (o: Option, memberId: string) => {
  const leg = o.people.find((p) => p.id === memberId);
  if (!leg) return Infinity;
  if (leg.subtotal !== undefined) return leg.subtotal ?? Infinity;
  if (leg.cost == null) return Infinity;
  return (cents(leg.cost) + cents(leg.lodgingAllocation ?? o.lodgingShare) + cents(o.daily) * o.nights) / 100;
};
export const groupTotal = (o: Option) => o.groupTotal !== undefined ? o.groupTotal ?? Infinity
  : o.people.length ? o.people.reduce((sum, p) => sum + cents(personTotal(o, p.id)), 0) / 100 : Infinity;
export const perPerson = (o: Option) => o.people.length ? groupTotal(o) / o.people.length : Infinity;
export const maxHours = (o: Option) => o.maxTravelHours !== undefined ? o.maxTravelHours ?? Infinity
  : o.people.length ? Math.max(...o.people.map((p) => p.hours ?? Infinity)) : Infinity;
export function sortOptions(opts: Option[], key: SortKey, w = 0.5): Option[] {
  const costs = opts.map(groupTotal), times = opts.map(maxHours);
  const norm = (value: number, values: number[]) => {
    if (!Number.isFinite(value)) return Infinity;
    const finite = values.filter(Number.isFinite);
    const lo = Math.min(...finite), hi = Math.max(...finite);
    return hi === lo ? 0 : (value - lo) / (hi - lo);
  };
  const weight = Math.min(1, Math.max(0, w));
  const score = (o: Option) => key === "cheapest" ? groupTotal(o)
    : key === "fastest" ? maxHours(o) : key === "fairest" ? o.fairestRank
    : Number.isFinite(groupTotal(o)) && Number.isFinite(maxHours(o))
      ? weight * norm(groupTotal(o), costs) + (1 - weight) * norm(maxHours(o), times) : Infinity;
  return [...opts].sort((a, b) => {
    const x = score(a), y = score(b);
    return (x < y ? -1 : x > y ? 1 : 0) || (key === "fairest" ? groupTotal(a) - groupTotal(b) : 0)
      || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  });
}
