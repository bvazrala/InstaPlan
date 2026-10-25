"use client";

import { Lock } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import PrivateCheckIn from "@/components/private/PrivateCheckIn";
import { NotIncluded, PersonCard } from "./Criteria";

/** Step 3, after the vote: see everyone's details and finish your own, then answer the questions only you can see. */
export default function CheckInView() {
  const { profile, participants, inactive, editField, trip } = useTrip();
  const going = participants.includes("me");
  const done = trip.checkedIn.filter((id) => participants.includes(id)).length;

  return (
    <div>
      <h3 className="text-lg font-semibold tracking-tight">Check-in</h3>
      <p className="mt-0.5 text-[13px] leading-snug text-muted">Review what everyone has shared and finish your own details, then add your private answers. {done} of {participants.length} have submitted.</p>

      <h4 className="mb-1 mt-6 text-[13px] font-medium text-muted">Shared with the group</h4>
      <ul className="divide-y divide-line">
        {participants.map((id) => (
          <PersonCard key={id} id={id} profile={profile} defaultOpen={id === "me"} onEdit={(field, v) => editField("me", field, v)} />
        ))}
      </ul>
      <NotIncluded people={inactive} />

      {going ? (
        <div className="mt-7 rounded-xl border border-line p-4 shadow-xs">
          <h4 className="mb-4 flex items-center gap-1.5 text-sm font-semibold"><Lock size={14} /> Only you</h4>
          <PrivateCheckIn />
        </div>
      ) : (
        <p className="mt-7 rounded-xl border border-dashed border-line p-4 text-center text-sm text-muted">Tap I&apos;m in above to take part in the check-in.</p>
      )}
    </div>
  );
}
