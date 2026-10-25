"use client";

import { usePlanner } from "@/lib/planner-context";
import PlannerPanel from "@/components/planner/PlannerPanel";
import { useTrip } from "@/lib/trip-context";
import { useLiveOptions } from "@/lib/live-options";
import OptionsView from "@/components/trip/options/OptionsView";
import { Button } from "@/components/ui/primitives";
import TripStart from "@/components/trip/TripStart";
import TripPanel from "@/components/trip/TripPanel";

export default function PanelBody({ onClose }: { onClose?: () => void }) {
  const { stage } = useTrip();
  const live = useLiveOptions();
  const planner = usePlanner();
  if (planner) return <PlannerPanel/>;
  if (live) {
    if (live.loading) return <p className="p-5 text-sm" role="status">Loading trip…</p>;
    if (!live.trip) return <div className="space-y-3 p-5"><h2 className="font-semibold">Plan a trip</h2>{live.error && <p role="alert" className="text-sm">{live.error}</p>}<Button onClick={() => void live.create()} disabled={live.busy}>Start a saved trip</Button><Button variant="outline" onClick={() => void live.refresh()}>Refresh</Button></div>;
    return <div className="space-y-4 p-5">
      <h2 className="text-lg font-semibold">{live.facts.find((fact) => fact.field === "Destination")?.value ?? "Group trip"}</h2>
      {live.trip.stage === "collecting" || live.trip.stage === "voting" ? <>
        <p className="text-sm text-muted">Trip details come from the group chat.</p>
        <ul className="space-y-2 text-sm">{live.facts.map((fact) => <li key={fact.id}><strong>{fact.field}:</strong> {fact.value}</li>)}</ul>
        {live.trip.stage === "collecting" ? <Button disabled={live.busy} onClick={() => void live.stage("voting")}>Call the vote</Button> : <>
          <p className="text-sm">{live.trip.yesVotes} of {live.trip.memberCount} voted yes</p>
          <Button disabled={live.busy} onClick={() => void live.vote(true)}>I’m in</Button><Button variant="outline" disabled={live.busy} onClick={() => void live.vote(false)}>Not going</Button>
        </>}
        {live.error && <p role="alert" className="text-sm text-red-800">{live.error}</p>}
      </> : <>
        {live.trip.stage === "checkin" && <p className="text-xs text-muted">{live.trip.checkinsDone} private check-ins submitted. Only shared trip options appear here.</p>}
        <OptionsView />
      </>}
    </div>;
  }
  return stage === "idle" ? <TripStart onClose={onClose} /> : <TripPanel onClose={onClose} />;
}
