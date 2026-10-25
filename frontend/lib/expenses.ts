// Expense math for the trip panel. Display only: Capital One Nessie moves the money.
import type { Expense } from "./trip-context";

export type Transfer = { from: string; to: string; amount: number };

/** What each person owes for the trip: the sum of their equal share of every expense they were part of. */
export const shareOf = (expenses: Expense[], id: string) =>
  expenses.reduce((n, e) => (e.split.includes(id) ? n + e.amount / e.split.length : n), 0);

export const paidBy = (expenses: Expense[], id: string) => expenses.reduce((n, e) => (e.payer === id ? n + e.amount : n), 0);

export const totalOf = (expenses: Expense[]) => expenses.reduce((n, e) => n + e.amount, 0);

/** Nets every expense into the fewest payments between the people involved. */
export function transfersFor(expenses: Expense[], ids: string[]): Transfer[] {
  const bal = Object.fromEntries(ids.map((id) => [id, paidBy(expenses, id) - shareOf(expenses, id)]));
  const owe = ids.filter((id) => bal[id] < -0.5).map((id) => ({ id, v: -bal[id] }));
  const due = ids.filter((id) => bal[id] > 0.5).map((id) => ({ id, v: bal[id] }));
  const out: Transfer[] = [];
  for (const d of owe) {
    for (const c of due) {
      const amt = Math.min(d.v, c.v);
      if (amt > 0.5) { out.push({ from: d.id, to: c.id, amount: Math.round(amt) }); d.v -= amt; c.v -= amt; }
    }
  }
  return out;
}
