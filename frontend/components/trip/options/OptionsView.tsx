"use client";

import Link from "next/link";

import { useMemo, useState } from "react";

import { ChevronRight } from "lucide-react";

import { sortOptions } from "@/lib/sort";

import { useLiveOptions } from "@/lib/live-options";

import type { PlanningInputs, SortKey } from "@/lib/types";

import { Button, inputCls, Segmented } from "@/components/ui/primitives";

import HeatMap from "./HeatMap";

import OptionCard from "./OptionCard";

const SORTS: { id: SortKey; label: string }[] = [

  { id: "cheapest", label: "Cheapest" }, { id: "fastest", label: "Fastest" },

  { id: "balanced", label: "Balanced" }, { id: "fairest", label: "Fairest" },

];



function CorrectInputs({ value, onSubmit }: { value: PlanningInputs; onSubmit: (value: PlanningInputs) => void }) {

  const live = useLiveOptions()!;

  const [inputs, setInputs] = useState<PlanningInputs>({ ...value, destinations: value.destinations.length ? value.destinations : [{ name: "", airports: [""] }] });

  const ids = [...new Set([...Object.keys(value.origins), ...live.status.missing.filter((key) => key.startsWith("origin:")).map((key) => key.slice(7))])];

  return <form className="space-y-3 rounded-xl border border-line bg-white p-4" onSubmit={(event) => { event.preventDefault(); onSubmit(inputs); }}>

    <p className="text-sm font-medium">Confirm the missing trip details</p>

    <div className="grid grid-cols-2 gap-3">

      <label className="text-xs">Destination arrival<input className={inputCls} type="date" required value={inputs.checkin ?? ""} onChange={(e) => setInputs({ ...inputs, checkin: e.target.value })} /></label>

      <label className="text-xs">Return departure<input className={inputCls} type="date" required value={inputs.checkout ?? ""} min={inputs.checkin ?? undefined} onChange={(e) => setInputs({ ...inputs, checkout: e.target.value })} /></label>

    </div>

    {inputs.destinations.map((destination, index) => <div className="grid grid-cols-2 gap-3" key={index}>

      <label className="text-xs">Destination name<input className={inputCls} required value={destination.name} onChange={(e) => setInputs({ ...inputs, destinations: inputs.destinations.map((d, i) => i === index ? { ...d, name: e.target.value } : d) })} /></label>

      <label className="text-xs">Arrival airport<input className={inputCls} required pattern="[A-Za-z]{3}" maxLength={3} value={destination.airports[0] ?? ""} onChange={(e) => setInputs({ ...inputs, destinations: inputs.destinations.map((d, i) => i === index ? { ...d, airports: [e.target.value.toUpperCase()] } : d) })} /></label>

    </div>)}

    {inputs.destinations.length < 6 && <Button type="button" variant="outline" onClick={() => setInputs({ ...inputs, destinations: [...inputs.destinations, { name: "", airports: [""] }] })}>Add destination</Button>}

    {ids.map((id) => <label key={id} className="block text-xs">Departure airport for {live.members[id]?.name ?? "Member"}<input className={inputCls} required pattern="[A-Za-z]{3}" maxLength={3} value={inputs.origins[id] ?? ""} onChange={(e) => setInputs({ ...inputs, origins: { ...inputs.origins, [id]: e.target.value.toUpperCase() } })} /></label>)}

    <Button type="submit" disabled={live.busy}>Confirm and search</Button>

  </form>;

}



export default function OptionsView({ wide = false }: { wide?: boolean }) {

  const live = useLiveOptions();

  const [sort, setSort] = useState<SortKey>("balanced");

  const [weight, setWeight] = useState(0.5);
  const [editing, setEditing] = useState(false);

  const options = live?.options;

  const sorted = useMemo(() => sortOptions(options ?? [], sort, weight), [options, sort, weight]);

  if (!live) return <p role="alert">Open a saved trip to view live options.</p>;

  if (live.loading) return <p role="status">Loading trip options…</p>;

  const allowed = live.trip?.stage === "checkin" || live.trip?.stage === "options";

  return <div className="space-y-4">

    {live.error && <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{live.error} <Button variant="outline" onClick={() => void live.refresh()}>Retry loading</Button><Link className="ml-2 underline" href="/login">Sign in</Link></div>}

    <div className="flex items-center justify-between gap-3">

      <div><h3 className="text-lg font-semibold">{sorted.length} options</h3><p className="text-xs text-muted">Flights and lodging for the whole group</p></div>

      {allowed && <Button variant="outline" disabled={live.busy} onClick={() => void live.generate()}>{live.busy ? "Searching…" : sorted.length ? "Refresh prices" : "Generate options"}</Button>}

    </div>

    {live.busy && <p role="status" className="text-sm text-muted">{live.status.status === "resolving" ? "Resolving trip details…" : "Searching flights and shared lodging…"}{sorted.length > 0 && " Previous options remain visible while prices refresh."}</p>}

    {live.status.status === "failed" && <p role="alert" className="text-sm text-red-800">{live.status.message ?? "Generation failed. Please retry."}</p>}

    {live.status.partial && <p className="text-sm text-amber-800">Some travel searches were unavailable. These options cover the results retrieved.</p>}

    {allowed && !live.busy && live.status.inputs && live.status.status !== "needs_input" && <Button variant="outline" onClick={() => setEditing(!editing)}>{editing ? "Close search details" : "Edit search details"}</Button>}
    {(live.status.status === "needs_input" || editing) && !live.busy && live.status.inputs && <CorrectInputs key={live.status.runId} value={live.status.inputs} onSubmit={(inputs) => { setEditing(false); void live.generate(inputs); }} />}

    {live.trip?.pickedOptionId && <div className="space-y-2"><p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">Your group has picked an option. The selection is saved.</p>{live.trip.stage === "picked" && <Button variant="outline" disabled={live.busy} onClick={() => void live.stage("options")}>Revise options</Button>}</div>}

    {sorted.length > 0 && <>

      <Segmented<SortKey> value={sort} onChange={setSort} options={SORTS} />

      {sort === "balanced" && <label className="flex items-center gap-3 text-xs text-muted">Time<input type="range" min={0} max={1} step={0.05} value={weight} onChange={(e) => setWeight(Number(e.target.value))} className="flex-1" aria-label="Balance time and cost" />Cost</label>}

      {!wide && live.trip && <Link href={`/trip/${live.trip.id}`} className="flex items-center justify-between rounded-lg border border-line px-4 py-3 text-sm">Compare side by side <ChevronRight size={16} /></Link>}

      {wide && <HeatMap options={sorted} />}

      <div className={wide ? "grid items-start gap-3 md:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>

        {sorted.map((option, index) => <OptionCard key={option.id} o={option} rank={index} picked={live.trip?.pickedOptionId === option.id} members={live.members} me={live.me} disabled={live.busy || !allowed} onPick={(ack) => void live.pick(option.id, ack)} />)}

      </div>

    </>}

    {!sorted.length && !live.busy && live.status.status === "ready" && <p role="status" className="rounded-lg border border-line p-4 text-sm">No matching options were found for this trip. Review the dates and destinations, then try again.</p>}

  </div>;

}
