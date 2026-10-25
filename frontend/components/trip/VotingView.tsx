"use client";

import { Check } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import { displayName } from "@/lib/trip-model";
import { Avatar } from "@/components/chat/Avatar";
import { Badge, Button, PrimaryButton, Progress, GhostButton } from "@/components/ui/primitives";
import { NotIncluded } from "./Criteria";

export default function VotingView() {
  const { trip, participants, inactive, profile, join, optOut, setStage } = useTrip();
  const yes = participants.filter((id) => trip.votes[id] === "yes").length;
  const majority = yes > participants.length / 2;
  const going = participants.includes("me");
  const dest = profile.group.destination?.value;
  const dates = profile.group.dates?.value;

  return (
    <div>
      <h3 className="text-lg font-semibold tracking-tight">Are we going?</h3>
      <p className="mt-0.5 text-sm text-muted">{[dest ?? "Destination not set", dates ?? "dates not set"].join(" · ")}</p>

      <div className="mt-4 flex gap-2">
        <Button className="flex-1" variant={trip.votes.me ? "default" : "outline"} onClick={join}>
          {trip.votes.me && <Check size={15} />} I&apos;m in
        </Button>
        <Button className="flex-1" variant={going ? "outline" : "default"} onClick={optOut}>Not going</Button>
      </div>
      {!going && <p className="mt-2 text-xs text-muted">You&apos;re not part of this plan. Tap I&apos;m in to rejoin.</p>}

      <div className="mb-2 mt-7 flex items-baseline justify-between">
        <h4 className="text-[13px] font-medium text-muted">Votes</h4>
        <span className="text-xs text-muted">{yes} of {participants.length} in</span>
      </div>
      <Progress value={participants.length ? (yes / participants.length) * 100 : 0} />
      <ul className="divide-y divide-line">
        {participants.map((id) => (
          <li key={id} className="flex items-center gap-3 py-2.5">
            <Avatar id={id} size={32} />
            <span className="flex-1 text-sm font-medium">{displayName(id)}</span>
            {trip.votes[id] === "yes" ? <Badge variant="success">In</Badge> : <span className="text-[13px] text-muted">Hasn&apos;t voted</span>}
          </li>
        ))}
      </ul>
      <NotIncluded people={inactive} />

      <div className="mt-6 space-y-2">
        {majority ? (
          <PrimaryButton onClick={() => setStage("checkin")}>Lock in trip</PrimaryButton>
        ) : (
          <p className="text-center text-xs text-muted">More than half of the people going need to be in to lock the trip.</p>
        )}
        <GhostButton onClick={() => setStage("collecting")}>Back to details</GhostButton>
      </div>
    </div>
  );
}
