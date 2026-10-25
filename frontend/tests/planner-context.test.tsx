import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { PlannerProvider, usePlanner } from "@/lib/planner-context";
const {api}=vi.hoisted(()=>({api:vi.fn()}));
vi.mock("@/lib/api",()=>({apiFetch:api}));
const plan=(id:string,revision=1)=>({tripId:id,title:id,revision});
function Probe(){const state=usePlanner()!;return <><span>{state.loading?"Loading":state.planner?.title??"No plan"}</span><span>{state.error}</span><button onClick={()=>void state.refresh()}>Refresh</button><button onClick={()=>void state.edit("attendance","going")}>Edit</button></>;}
beforeEach(()=>{api.mockReset();});
it("recovers from fetch failures and refreshes on reconnect events",async()=>{
  api.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(plan("Plan A"));
  render(<PlannerProvider chatId="a"><Probe/></PlannerProvider>);
  await screen.findByText("offline");fireEvent.click(screen.getByText("Refresh"));
  await screen.findByText("Plan A");expect(screen.queryByText("offline")).not.toBeInTheDocument();
  const before=api.mock.calls.length;
  act(()=>window.dispatchEvent(new Event("online")));
  await waitFor(()=>expect(api.mock.calls.length).toBeGreaterThan(before));
});
it("a late response cannot replace the next chat's planner",async()=>{
  let finish:(value:unknown)=>void=()=>{};
  api.mockImplementation(async(path:string)=>path.includes('/a/')?new Promise(resolve=>{finish=resolve;}):plan("Plan B"));
  const {rerender}=render(<PlannerProvider chatId="a"><Probe/></PlannerProvider>);
  await waitFor(()=>expect(api).toHaveBeenCalled());
  rerender(<PlannerProvider chatId="b"><Probe/></PlannerProvider>);
  await screen.findByText("Plan B");await act(async()=>finish(plan("Plan A")));
  expect(screen.queryByText("Plan A")).not.toBeInTheDocument();
});
it("older revisions do not overwrite a manual correction",async()=>{
  api.mockResolvedValueOnce(plan("Plan",2));
  render(<PlannerProvider chatId="a"><Probe/></PlannerProvider>);await screen.findByText("Plan");
  api.mockResolvedValueOnce({...plan("Old",1),tripId:"Plan"});
  fireEvent.click(screen.getByText("Refresh"));
  await waitFor(()=>expect(api).toHaveBeenCalledTimes(2));expect(screen.queryByText("Old")).not.toBeInTheDocument();
});
