"use client";

import { useState } from "react";
import { Landmark } from "lucide-react";
import { useTrip } from "@/lib/trip-context";
import { money } from "@/lib/format";
import { Card, Chip, Label, PrimaryButton } from "@/components/ui/primitives";
import PrivacyBanner from "./PrivacyBanner";

const DIET = ["Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free", "Nut allergy", "No seafood"];
const ACCESS = ["Step-free access", "Limited walking", "No flying"];

/**
 * Private check-in (R9, R11, R22). Everything in components/private/ renders data only its owner may see.
 * TODO: present these questions as messages in the member's private assistant thread, and load and save
 * them through GET/PUT /trips/{tripId}/me/private (see docs/api-contract.md).
 */
export default function PrivateCheckIn() {
  const { setStage, ceiling, setCeiling } = useTrip();
  const [diet, setDiet] = useState<string[]>(["No seafood"]);
  const [access, setAccess] = useState<string[]>([]);
  const [linked, setLinked] = useState(false);
  const toggle = (arr: string[], set: (a: string[]) => void, v: string) => set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  return (
    <div className="space-y-4">
      <PrivacyBanner />

      <div>
        <Label>Budget cap for this trip</Label>
        <div className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2.5">
          <span className="text-sm text-muted">$</span>
          <input type="number" value={ceiling} onChange={(e) => setCeiling(Number(e.target.value))} className="w-full bg-transparent text-lg font-bold outline-none" />
        </div>
        <input type="range" min={200} max={1500} step={10} value={ceiling} onChange={(e) => setCeiling(Number(e.target.value))} className="mt-2 w-full accent-[#6d3df0]" />
      </div>

      <Card className="border-sky-100 bg-sky-50/60">
        <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-sky-800"><Landmark size={13} /> Capital One · Nessie (sandbox)</p>
        {linked ? (
          <>
            <p className="text-[13px] font-semibold">Suggested safe-to-spend: {money(620)}</p>
            <p className="mb-2 text-xs text-muted">Rent of $890 is due Dec 1, before the trip, so we left a cushion.</p>
            <div className="flex gap-2">
              <Chip on onClick={() => setCeiling(620)}>Accept {money(620)}</Chip>
              <Chip>Override</Chip>
            </div>
          </>
        ) : (
          <>
            <p className="mb-2 text-xs text-muted">Link an account to get a suggested ceiling with a reason.</p>
            <Chip onClick={() => setLinked(true)}>Link account</Chip>
          </>
        )}
      </Card>

      <div>
        <Label>Dietary needs</Label>
        <div className="flex flex-wrap gap-1.5">{DIET.map((d) => <Chip key={d} on={diet.includes(d)} onClick={() => toggle(diet, setDiet, d)}>{d}</Chip>)}</div>
      </div>
      <div>
        <Label>Accessibility</Label>
        <div className="flex flex-wrap gap-1.5">{ACCESS.map((d) => <Chip key={d} on={access.includes(d)} onClick={() => toggle(access, setAccess, d)}>{d}</Chip>)}</div>
      </div>
      <div>
        <Label>Private no-gos</Label>
        <textarea rows={2} placeholder="Anything you'd rather not say in the chat…" className="w-full resize-none rounded-xl bg-surface px-3 py-2.5 text-sm outline-none placeholder:text-muted" />
      </div>

      <PrimaryButton onClick={() => setStage("options")}>Submit &amp; generate options</PrimaryButton>
      <p className="text-center text-[11px] text-muted">3 of 4 members have submitted</p>
    </div>
  );
}
