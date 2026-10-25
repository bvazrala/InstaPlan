import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import PlannerPanel, { PlannerApprovalCard } from "@/components/planner/PlannerPanel";
import PlannerRecommendations from "@/components/planner/PlannerRecommendations";
import { PlannerEntry, PublicPerspective } from "@/components/planner/PlannerEntry";
import { option } from "./fixtures";
const {state}=vi.hoisted(()=>({state:{current:null as unknown}}));
vi.mock("@/lib/planner-context",()=>({usePlanner:()=>state.current}));
vi.mock("@/lib/trip-context",()=>({useTrip:()=>({setPanelOpen:vi.fn()})}));
const member={id:"alice",name:"Alice",handle:"alice",hue:260};
function makeState(overrides={}) {return {me:"alice",speaker:"alice",members:{alice:member,bob:{...member,id:"bob",name:"Bob"}},demoMode:true,busy:false,error:null,
  respond:vi.fn(),reset:vi.fn(),vote:vi.fn(),edit:vi.fn(),pick:vi.fn(),action:vi.fn(),pricing:vi.fn(),setSpeaker:vi.fn(),setCreating:vi.fn(),create:vi.fn(async()=>true),creating:false,
  planner:{tripId:"p",title:"Dinner",topic:"Dining",status:"collecting",pricedMembers:["alice"],pickedId:null,
    template:{where:{searchArea:"Austin",origins:{}},when:{agreed:null,flexibility:{}},preferences:{},hardConstraints:{},cluster:{},sources:{}},
    attendance:{alice:{status:"going",condition:null,inferred:false},bob:{status:"conditional",condition:null,inferred:true}},missing:[],listening:"idle",provenance:{},
    poll:{ready:true,eligible:["alice","bob"],approvals:[] as string[],changes:[],required:1,threshold:.5},
    generation:{status:"idle",runId:null as string|null},recommendations:{kind:"venues",venues:[]}},...overrides};}
beforeEach(()=>{state.current=makeState();});
it("uses a binary RSVP instead of the old change-request vote",()=>{
  const s=makeState();state.current=s;render(<PlannerApprovalCard/>);
  fireEvent.click(screen.getByRole("button",{name:"Not coming"}));
  expect(s.respond).toHaveBeenCalledWith(false);expect(s.edit).not.toHaveBeenCalled();
});
it("waits for readiness before showing an automatic approval card",()=>{
  const s=makeState();s.planner.poll.ready=false;state.current=s;render(<PlannerApprovalCard/>);
  expect(screen.queryByRole("button",{name:"Yes, I’m going"})).not.toBeInTheDocument();
});
it("the public perspective switcher never changes the private identity",()=>{
  const s=makeState();state.current=s;render(<PublicPerspective/>);
  fireEvent.click(screen.getByRole("button",{name:"Bob"}));expect(s.setSpeaker).toHaveBeenCalledWith("bob");
  expect(s.me).toBe("alice");expect(screen.getByRole("button",{name:"Reset demo"})).toBeVisible();
});
it("requires title and topic when creating a planner",()=>{
  const s=makeState({creating:true});state.current=s;render(<PlannerEntry/>);
  expect(screen.getByLabelText("Title")).toBeRequired();expect(screen.getByRole("radio",{name:"Dining"})).toBeChecked();
  expect(screen.getByRole("radio",{name:"Travel"})).toBeInTheDocument();
});
it("surfaces failures and retries without inventing recommendations",()=>{
  const s=makeState();s.planner.generation={status:"failed",runId:"r"};state.current=s;render(<PlannerRecommendations/>);
  fireEvent.click(screen.getByRole("button",{name:"Retry recommendations"}));expect(s.action).toHaveBeenCalledWith("retry");
  expect(screen.queryByRole("article")).not.toBeInTheDocument();
});
it("renders unknown venue costs and blocks unverified hard requirements",()=>{
  const s=makeState();Object.assign(s.planner,{status:"approved",generation:{status:"ready"},recommendations:{kind:"venues",venues:[{id:"v",title:"Cafe",address:null,rating:4.6,priceLevel:null,url:null,provider:"SerpApi",retrievedAt:"2026-10-25T12:00:00Z",fit:null,evidence:[],warnings:["Exact cost unknown"],pickEligible:false}]}});state.current=s;
  render(<PlannerRecommendations/>);expect(screen.getByText(/Price unknown/)).toBeVisible();expect(screen.getByText("Fit unknown")).toBeVisible();expect(screen.getByRole("button",{name:"Verification needed"})).toBeDisabled();
});
it("uses travel sorts locally and enforces capacity acknowledgment",()=>{
  const s=makeState();Object.assign(s.planner,{topic:"Travel",status:"approved",generation:{status:"ready"},recommendations:{kind:"travel",options:[option({id:"cheap",title:"Cheap",groupTotal:600,maxTravelHours:9}),option({id:"fast",title:"Fast",groupTotal:900,maxTravelHours:2})]}});state.current=s;
  render(<PlannerRecommendations/>);fireEvent.change(screen.getByLabelText("Sort options"),{target:{value:"fastest"}});
  expect(screen.getAllByRole("article")[0]).toHaveAttribute("aria-label","Fast");
  fireEvent.change(screen.getByLabelText("Sort options"),{target:{value:"cheapest"}});expect(screen.getAllByRole("article")[0]).toHaveAttribute("aria-label","Cheap");
  expect(s.action).not.toHaveBeenCalled();
  const first=screen.getAllByRole("article")[0];fireEvent.click(first.querySelector('input[type=checkbox]')!);
  fireEvent.click(within(first).getByRole('button',{name:'Pick this option'}));
  expect(s.pick).toHaveBeenCalledWith('cheap',true);
});


it("opens as a readable plan with corrections tucked away",()=>{
  const s=makeState();state.current=s;render(<PlannerPanel/>);
  expect(screen.getByRole('region',{name:'Plan summary'})).toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Edit details'}));
  expect(screen.getByRole('textbox',{name:'Public preferences'})).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Done'}));
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});
it("keeps a confirmed summary after approvals instead of leaving a frozen form",()=>{
  const s=makeState();s.planner.status='approved';s.planner.poll.approvals=['alice'];state.current=s;
  render(<PlannerPanel/>);
  expect(screen.getByText('Plan confirmed')).toBeVisible();
  expect(screen.getByText(/recommendations for 1 going member/)).toBeVisible();
  expect(screen.queryByRole('button',{name:'Edit details'})).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});
