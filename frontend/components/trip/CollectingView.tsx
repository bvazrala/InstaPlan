"use client";

import { useTrip } from "@/lib/trip-context";
import { filledFields, GROUP_FIELDS, totalFields } from "@/lib/trip-model";
import { PrimaryButton, Progress } from "@/components/ui/primitives";
import { FieldRow, NotIncluded, PersonCard } from "./Criteria";

/** Step 1: criteria the assistant has picked up from the chat so far. You can edit your own and the shared trip fields. */
export default function CollectingView() {
  const { profile, participants, inactive, editField, setStage } = useTrip();
  const filled = filledFields(profile, participants);
  const total = totalFields(participants);
  const missing = total - filled;

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold tracking-tight">Trip details</h3>
        <span className="text-xs text-muted">{filled} of {total} filled</span>
      </div>
      <div className="mt-2"><Progress value={(filled / total) * 100} /></div>
      <p className="mt-2 text-[13px] leading-snug text-muted">Filled in from your messages. Correct your own details or add what hasn&apos;t come up yet. You can see everyone else&apos;s.</p>

      <h4 className="mb-1 mt-6 text-[13px] font-medium text-muted">Trip</h4>
      <div className="divide-y divide-line">
        {GROUP_FIELDS.map((f) => <FieldRow key={f.id} spec={f.spec} entry={profile.group[f.id]} onSave={(v) => editField("group", f.id, v)} />)}
      </div>

      <h4 className="mb-1 mt-6 text-[13px] font-medium text-muted">Everyone going</h4>
      <ul className="divide-y divide-line">
        {participants.map((id) => (
          <PersonCard key={id} id={id} profile={profile} defaultOpen={id === "me"} onEdit={(field, v) => editField("me", field, v)} />
        ))}
      </ul>
      <NotIncluded people={inactive} />

      <PrimaryButton onClick={() => setStage("voting")} className="mt-6">Start vote</PrimaryButton>
      {missing > 0 && <p className="mt-2 text-center text-xs text-muted">{missing} details are still open. Everyone can finish theirs after the vote.</p>}
    </div>
  );
}
