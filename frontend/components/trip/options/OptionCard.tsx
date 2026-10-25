"use client";
import { useState } from "react";
import { Check, ChevronDown, ExternalLink } from "lucide-react";
import { groupTotal, maxHours, perPerson, personTotal } from "@/lib/sort";
import type { Member, Option } from "@/lib/types";
import { Avatar } from "@/components/chat/Avatar";
import { Button } from "@/components/ui/primitives";
import FitPill from "./FitPill";

export const amount = (value: number | null | undefined, currency = "USD") => value != null && Number.isFinite(value)
  ? new Intl.NumberFormat(undefined, { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value) : "Unknown";
const hours = (value: number | null) => value != null && Number.isFinite(value) ? `${Number(value.toFixed(2))}h` : "Unknown";
const safeListing = (value?: string | null) => { try { const url = new URL(value ?? ""); return ["http:", "https:"].includes(url.protocol) ? url.href : null; } catch { return null; } };
export default function OptionCard({ o, rank, onPick, picked, disabled = false, members = {}, me = "" }: {
  o: Option; rank: number; onPick: (acknowledge: boolean) => void; picked: boolean; disabled?: boolean;
  members?: Record<string, Member>; me?: string;
}) {
  const [open, setOpen] = useState(rank === 0);
  const [acknowledged, setAcknowledged] = useState(false);
  const listing = safeListing(o.listingUrl);
  return (
    <article className={`overflow-hidden rounded-xl border bg-white shadow-xs ${picked ? "border-neutral-900" : "border-line"}`} aria-label={o.title}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0"><p className="text-xs text-muted">{o.place} · {o.dates}</p><h4 className="text-[17px] font-semibold leading-tight">{o.title}</h4></div>
          <FitPill fit={o.fit} />
        </div>
        <p className="mt-1 text-xs text-muted">{o.certainty}</p>
        {o.feasibility === "unverified" && <p className="mt-2 text-xs font-medium text-amber-800">Some details are unverified</p>}
        <dl className="mt-4 grid grid-cols-3 divide-x divide-line text-center">
          {[["Average each", amount(perPerson(o), o.currency)], ["Group total", amount(groupTotal(o), o.currency)], ["Longest round trip", hours(maxHours(o))]].map(([label, value]) => (
            <div key={label} className="min-w-0 px-1"><dt className="text-[11px] text-muted">{label}</dt><dd className="break-words text-sm font-semibold">{value}</dd></div>
          ))}
        </dl>
        <p className="mt-2 text-[11px] text-muted">Flights and lodging · excludes meals, activities and ground travel</p>
        <button onClick={() => setOpen(!open)} aria-expanded={open} className="mt-4 flex w-full items-center justify-between border-t border-line pt-3 text-[13px] font-semibold">
          Cost breakdown <ChevronDown size={16} className={`text-muted transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open && <div className="mt-2">
          <p className="mb-2 text-xs text-muted">{o.lodging} · {amount(o.lodgingTotal, o.currency)} shared for {o.nights} nights</p>
          <ul className="space-y-2">{o.people.map((person) => <li key={person.id} className="flex items-center gap-2 text-[13px]">
            <Avatar id={person.id} size={24} members={members} />
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block font-medium">{person.id === me ? "You" : members[person.id]?.name ?? "Member"}</span>
              <span className="block text-xs text-muted">{person.origin} · round trip {hours(person.hours)}</span>
              <span className="block text-xs text-muted">Flight {amount(person.cost, o.currency)} + stay {amount(person.lodgingAllocation, o.currency)}</span>
            </span><span className="font-semibold">{amount(personTotal(o, person.id), o.currency)}</span>
          </li>)}</ul>
          <p className="pt-3 text-[11px] text-muted">{o.priceCoverage === "quoted_with_taxes" ? "Lodging quote includes taxes and fees" : "Lodging estimate before taxes and fees"}</p>
          <p className="text-[11px] text-muted">{o.pricedAt ? `Quoted ${new Date(o.pricedAt).toLocaleString()}` : "Quote time unavailable"} · availability may change</p>
        </div>}
        {o.warnings?.includes("requirements_unverified") && <p className="mt-3 text-xs text-amber-800">Some trip requirements still need verification before this option can be picked.</p>}
        {o.capacityAckRequired && !picked && <label className="mt-3 flex items-start gap-2 text-xs text-amber-900">
          <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} className="mt-0.5" />
          I understand lodging capacity is unverified and must be confirmed before booking.
        </label>}
        <div className="mt-4 flex gap-2">
          <Button className="flex-1" variant={picked ? "secondary" : "default"} disabled={disabled || picked || !o.pickEligible || (!!o.capacityAckRequired && !acknowledged)} onClick={() => onPick(acknowledged)}>
            {picked ? <><Check size={15} /> Picked</> : o.pickEligible ? "Pick this option" : "Verification needed"}
          </Button>
          {listing && <a href={listing} target="_blank" rel="noopener noreferrer" aria-label={`Open listing for ${o.lodging}`} className="inline-flex size-9 items-center justify-center rounded-md border border-line"><ExternalLink size={16} /></a>}
        </div>
      </div>
    </article>
  );
}
