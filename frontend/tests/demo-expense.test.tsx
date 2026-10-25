import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import DemoExpenseSplit, { equalShares, expenseCents } from "@/components/planner/DemoExpenseSplit";
const { state } = vi.hoisted(() => ({ state: { current: null as unknown } }));
vi.mock("@/lib/planner-context", () => ({ usePlanner: () => state.current }));
const members = Object.fromEntries(["alice", "bob", "cara", "dan"].map(id => [id, { id, name: id, handle: id, hue: 20 }]));
function demo() { return { demoMode: true, speaker: "alice", members, planner: { pricedMembers: ["alice", "bob", "cara"] } }; }
beforeEach(() => { state.current = demo(); });
it("allocates every cent exactly once with stable participant ordering", () => {
  const shares = equalShares(10001, ["cara", "bob", "alice", "alice"]);
  expect(shares).toEqual({ alice: 3334, bob: 3334, cara: 3333 });
  expect(Object.values(shares).reduce((sum, value) => sum + value, 0)).toBe(10001);
  expect(equalShares(100, [])).toEqual({});
  expect(expenseCents("100.01")).toBe(10001);
  for (const invalid of ["0", "-1", "NaN", "1.001", "1e3", "1000000", ""]) expect(expenseCents(invalid)).toBeNull();
});
it("simulates speaker payments without requests and prevents duplicate payments", () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  const s = demo(); state.current = s;
  const view = render(<DemoExpenseSplit place="Garden Cafe"/>);
  expect(screen.getByText(/No real money moves/)).toBeVisible();
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
  expect(screen.queryByText("dan")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Mock payment method"), { target: { value: "Demo Venmo" } });
  fireEvent.click(screen.getByRole("button", { name: "Simulate prepaying $40.00" }));
  expect(screen.getByRole("button", { name: "Your share is prepaid" })).toBeDisabled();
  expect(screen.getByLabelText("Shared expense (USD)")).toBeDisabled();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "4000");
  s.speaker = "bob"; view.rerender(<DemoExpenseSplit place="Garden Cafe"/>);
  fireEvent.click(screen.getByRole("button", { name: "Simulate prepaying $40.00" }));
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "8000");
  expect(within(screen.getAllByRole("listitem")[0]).getByText(/Demo Venmo/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Reset mock payments" }));
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
  expect(screen.getByLabelText("Shared expense (USD)")).toBeEnabled();
  expect(fetch).not.toHaveBeenCalled(); fetch.mockRestore();
});
it("validates editable amounts and excludes nonparticipants from payment actions", () => {
  const s = demo(); state.current = s;
  const view = render(<DemoExpenseSplit place="Cafe"/>);
  fireEvent.change(screen.getByLabelText("Shared expense (USD)"), { target: { value: "12.001" } });
  expect(screen.getByRole("alert")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Simulate prepaying/ })).not.toBeInTheDocument();
  s.speaker = "dan"; view.rerender(<DemoExpenseSplit place="Cafe"/>);
  expect(screen.getByText(/Only going members/)).toBeVisible();
});
it("keeps mock payment controls out of normal-user flows", () => {
  state.current = { ...demo(), demoMode: false };
  render(<DemoExpenseSplit place="Cafe"/>);
  expect(screen.queryByRole("region", { name: "Demo expense split" })).not.toBeInTheDocument();
});
