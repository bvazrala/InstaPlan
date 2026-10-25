"use client";

import { useTrip } from "@/lib/trip-context";
import { Chip, Label, PrimaryButton, textareaCls } from "@/components/ui/primitives";
import PrivacyBanner from "./PrivacyBanner";

const ACCESS = ["Step-free access", "Limited walking", "No flying"];

/**
 * The logged-in user's private answers for this trip (R9, R22). Everything in components/private/ renders data only
 * its owner may see. The budget is whatever you type: nothing infers it.
 * TODO: load and save through GET/PUT /trips/{tripId}/me/private (see docs/api-contract.md).
 */
export default function PrivateCheckIn() {
  const { trip, update, setStage } = useTrip();
  const { budget, access, noGos } = trip.mine;
  const set = (p: Partial<typeof trip.mine>) => update((t) => ({ mine: { ...t.mine, ...p } }));
  const toggle = (v: string) => set({ access: access.includes(v) ? access.filter((x) => x !== v) : [...access, v] });
  const ready = Number(budget) > 0;

  const submit = () => {
    update((t) => ({ checkedIn: t.checkedIn.includes("me") ? t.checkedIn : [...t.checkedIn, "me"] }));
    setStage("options");
  };

  return (
    <div className="space-y-5">
      <PrivacyBanner />

      <div>
        <Label>Most you want to spend</Label>
        <div className="flex h-10 items-center gap-1 rounded-md border border-line bg-white px-3 shadow-xs focus-within:border-neutral-400 focus-within:ring-[3px] focus-within:ring-neutral-200">
          <span className="text-base font-semibold text-muted">$</span>
          <input type="number" min={0} inputMode="numeric" value={budget} onChange={(e) => set({ budget: e.target.value })} placeholder="0" className="w-full bg-transparent text-base font-semibold outline-none placeholder:text-neutral-300" aria-label="Budget" />
        </div>
      </div>

      <div>
        <Label>Access needs</Label>
        <div className="flex flex-wrap gap-1.5">{ACCESS.map((a) => <Chip key={a} on={access.includes(a)} onClick={() => toggle(a)}>{a}</Chip>)}</div>
      </div>

      <div>
        <Label>Anything else to avoid</Label>
        <textarea value={noGos} onChange={(e) => set({ noGos: e.target.value })} rows={2} placeholder="Only the trip assistant sees this" className={textareaCls} />
      </div>

      <PrimaryButton onClick={submit} disabled={!ready}>{trip.checkedIn.includes("me") ? "Update and see options" : "Submit and see options"}</PrimaryButton>
      {!ready && <p className="text-center text-xs text-muted">Enter a budget to submit.</p>}
    </div>
  );
}
