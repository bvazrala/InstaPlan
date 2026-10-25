"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { TripProvider, useTrip } from "@/lib/trip-context";
import OptionsView from "./options/OptionsView";

function Header({ tripId }: { tripId: string }) {
  const { profile, members } = useTrip();
  const dest = profile.group.destination?.value ?? "Trip";
  const dates = profile.group.dates?.value ?? "dates not set";
  return (
    <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-line bg-white px-4 md:px-6">
      <Link href="/" aria-label="Back to chat"><ArrowLeft size={20} /></Link>
      <div className="leading-tight">
        <p className="text-sm font-semibold" data-trip-id={tripId}>{dest} · Trip options</p>
        <p className="text-[11px] text-muted">{dates} · {members.length} people</p>
      </div>
    </header>
  );
}

/** Companion trip page: full heat map + side-by-side comparison (the "link out" from chat). */
export default function TripPage({ tripId }: { tripId: string }) {
  // TODO: load this trip's options with apiFetch(`/trips/${tripId}/options`) instead of demo data.
  return (
    <TripProvider>
      <div className="min-h-dvh bg-[#f7f7f8]">
        <Header tripId={tripId} />
        <main className="mx-auto max-w-[1400px] p-4 md:p-6">
          <OptionsView wide />
        </main>
      </div>
    </TripProvider>
  );
}
