import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import OptionCard from "@/components/trip/options/OptionCard";
import OptionsView from "@/components/trip/options/OptionsView";
import { groupTotal, personTotal, sortOptions } from "@/lib/sort";
import { option, status, trip } from "./fixtures";
const { state } = vi.hoisted(() => ({ state: { live: null as unknown } }));
vi.mock("@/lib/live-options", () => ({ useLiveOptions: () => state.live }));
const members = { alice: { id: "alice", name: "Alice", handle: "alice", hue: 260, origin: "AUS" } };
const makeLive = (overrides = {}) => ({ trip, options: [option()], status, members, me: "alice", loading: false,
  error: null, busy: false, generate: vi.fn(), refresh: vi.fn(), pick: vi.fn(), stage: vi.fn(), ...overrides });
beforeEach(() => { state.live = makeLive(); });

describe("exact costs and ranking", () => {
  it("preserves the individual remainder cents and full group total", () => {
    const value = option();
    expect(groupTotal(value)).toBe(700.01);
    expect(personTotal(value, "cara")).toBe(333.33);
    expect(personTotal(value, "missing")).toBe(Infinity);
  });
  it("implements all strategies and stable ties", () => {
    const cheap = option({ id: "cheap", groupTotal: 600, maxTravelHours: 9, fairestRank: 2 });
    const fast = option({ id: "fast", groupTotal: 800, maxTravelHours: 3, fairestRank: 1 });
    expect(sortOptions([fast, cheap], "cheapest")[0].id).toBe("cheap");
    expect(sortOptions([cheap, fast], "fastest")[0].id).toBe("fast");
    expect(sortOptions([cheap, fast], "fairest")[0].id).toBe("fast");
    expect(sortOptions([cheap, fast], "balanced", 0)[0].id).toBe("fast");
    expect(sortOptions([cheap, fast], "balanced", 1)[0].id).toBe("cheap");
    expect(sortOptions([option({ id: "z" }), option({ id: "a" })], "balanced")[0].id).toBe("a");
    expect(sortOptions([option({ id: "unknown", maxTravelHours: null }), fast], "fastest")[1].id).toBe("unknown");
  });
});

it("requires capacity acknowledgment and passes it to the real pick action", () => {
  const pick = vi.fn();
  render(<OptionCard o={option()} rank={0} picked={false} onPick={pick} members={members} me="alice" />);
  expect(screen.getByRole("button", { name: "Pick this option" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Pick this option" }));
  expect(pick).toHaveBeenCalledWith(true);
  expect(screen.getByText("You")).toBeVisible();
  expect(screen.getByText(/333[.,]33/)).toBeVisible();
  expect(screen.queryByText(/Oct 24, 9:41/)).not.toBeInTheDocument();
});

it("blocks hard unverified requirements and unsafe listing links", () => {
  render(<OptionCard o={option({ pickEligible: false, capacityAckRequired: false, listingUrl: "javascript:alert(1)", warnings: ["requirements_unverified"] })} rank={0} picked={false} onPick={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Verification needed" })).toBeDisabled();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("renders actual provider links safely", () => {
  render(<OptionCard o={option({ listingUrl: "https://example.com/stay" })} rank={0} picked={false} onPick={vi.fn()} />);
  expect(screen.getByRole("link")).toHaveAttribute("rel", "noopener noreferrer");
});

it("renders loading, failure recovery and successful empty results", () => {
  const { rerender } = render(<OptionsView />);
  const live = makeLive({ loading: true }); state.live = live;
  rerender(<OptionsView />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading trip options");
  state.live = makeLive({ options: [], status: { ...status, status: "failed", message: "Provider unavailable" } });
  rerender(<OptionsView />);
  expect(screen.getByRole("alert")).toHaveTextContent("Provider unavailable");
  const failed = state.live as ReturnType<typeof makeLive>;
  fireEvent.click(screen.getByRole("button", { name: "Generate options" }));
  expect(failed.generate).toHaveBeenCalled();
  state.live = makeLive({ options: [] }); rerender(<OptionsView />);
  expect(screen.getByRole("status")).toHaveTextContent("No matching options");
});

it("supports sort tabs, the balance slider and a real comparison URL", () => {
  const cheap = option({ id: "cheap", title: "Cheap trip", groupTotal: 600, maxTravelHours: 9 });
  const fast = option({ id: "fast", title: "Fast trip", groupTotal: 800, maxTravelHours: 3 });
  const live = makeLive({ options: [fast, cheap] }); state.live = live;
  render(<OptionsView />);
  fireEvent.click(screen.getByRole("tab", { name: "Cheapest" }));
  expect(screen.getAllByRole("article")[0]).toHaveAttribute("aria-label", "Cheap trip");
  fireEvent.click(screen.getByRole("tab", { name: "Fastest" }));
  expect(screen.getAllByRole("article")[0]).toHaveAttribute("aria-label", "Fast trip");
  fireEvent.click(screen.getByRole("tab", { name: "Balanced" }));
  fireEvent.change(screen.getByRole("slider"), { target: { value: "1" } });
  expect(screen.getAllByRole("article")[0]).toHaveAttribute("aria-label", "Cheap trip");
  expect(live.generate).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: /Compare side by side/ })).toHaveAttribute("href", "/trip/trip-a");
});

it("shows unscored categories in the comparison and partial availability", () => {
  state.live = makeLive({ status: { ...status, partial: true } });
  render(<OptionsView wide />);
  expect(screen.getByRole("table")).toBeVisible();
  expect(screen.getAllByText("Not evaluated")).toHaveLength(2);
  expect(screen.getByText(/Some travel searches were unavailable/)).toBeVisible();
});

it("submits missing public inputs without introducing private fields", () => {
  const live = makeLive({ options: [], status: { ...status, status: "needs_input", missing: ["origin:alice"],
    inputs: { destinations: [], checkin: null, checkout: null, origins: {} } } }); state.live = live;
  render(<OptionsView />);
  fireEvent.change(screen.getByLabelText("Destination arrival"), { target: { value: "2030-11-05" } });
  fireEvent.change(screen.getByLabelText("Return departure"), { target: { value: "2030-11-09" } });
  fireEvent.change(screen.getByLabelText("Destination name"), { target: { value: "New York City" } });
  fireEvent.change(screen.getByLabelText("Arrival airport"), { target: { value: "JFK" } });
  fireEvent.change(screen.getByLabelText("Departure airport for Alice"), { target: { value: "AUS" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirm and search" }));
  expect(live.generate).toHaveBeenCalledWith(expect.objectContaining({ origins: { alice: "AUS" }, checkin: "2030-11-05" }));
  expect(JSON.stringify(live.generate.mock.calls)).not.toMatch(/budget|private|ceiling/i);
});
