import { act, render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { LiveOptionsProvider, useLiveOptions } from "@/lib/live-options";
import { option, status, trip } from "./fixtures";
const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("@/lib/api", () => ({ apiFetch: api, ApiError: class extends Error {} }));
vi.mock("@/lib/supabase", () => ({ getClientSession: async () => null }));
function Probe() {
  const live = useLiveOptions()!;
  return <><span>{live.loading ? "Loading" : live.trip?.id ?? "No trip"}</span><span>{live.options[0]?.title}</span>
    <span>{live.error}</span><button onClick={() => void live.refresh()}>Retry</button>
    <button onClick={() => void live.pick("a", true)}>Pick</button></>;
}
beforeEach(() => {
  api.mockReset();
  api.mockImplementation(async (path: string) => {
    if (path.endsWith("/trips/active")) return { ...trip, id: path.includes("chat-b") ? "trip-b" : "trip-a" };
    if (path.endsWith("/options/status")) return status;
    if (path.endsWith("/options")) return [option({ title: path.includes("trip-b") ? "Option B" : "Option A" })];
    if (path.endsWith("/facts") || path.endsWith("/members")) return [];
    return trip;
  });
});
it("loads persisted trips, picks through the API, and isolates chat switches", async () => {
  const { rerender } = render(<LiveOptionsProvider chatId="chat-a"><Probe /></LiveOptionsProvider>);
  expect(screen.getByText("Loading")).toBeVisible();
  await screen.findByText("Option A");
  fireEvent.click(screen.getByText("Pick"));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/trips/trip-a/pick", expect.objectContaining({ body: JSON.stringify({ optionId: "a", acknowledgeCapacity: true }) })));
  rerender(<LiveOptionsProvider chatId="chat-b"><Probe /></LiveOptionsProvider>);
  expect(screen.queryByText("Option A")).not.toBeInTheDocument();
  await screen.findByText("Option B");
  expect(screen.getByText("trip-b")).toBeVisible();
});
it("recovers from fetch errors and refreshes when an options event arrives", async () => {
  api.mockRejectedValueOnce(new Error("offline"));
  render(<LiveOptionsProvider chatId="chat-a"><Probe /></LiveOptionsProvider>);
  await screen.findByText("Could not load this trip. Please retry.");
  fireEvent.click(screen.getByText("Retry"));
  await screen.findByText("Option A");
  const before = api.mock.calls.length;
  await act(async () => window.dispatchEvent(new Event("instaplan:trip")));
  await waitFor(() => expect(api.mock.calls.length).toBeGreaterThan(before));
});
it("ignores a late response from the previous chat", async () => {
  let finish: (value: unknown) => void = () => {};
  api.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  const { rerender } = render(<LiveOptionsProvider chatId="chat-a"><Probe /></LiveOptionsProvider>);
  rerender(<LiveOptionsProvider chatId="chat-b"><Probe /></LiveOptionsProvider>);
  await screen.findByText("Option B");
  await act(async () => finish(trip));
  expect(screen.queryByText("Option A")).not.toBeInTheDocument();
  expect(screen.getByText("trip-b")).toBeVisible();
});
