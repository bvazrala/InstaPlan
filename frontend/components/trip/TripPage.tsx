"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { TripProvider } from "@/lib/trip-context";
import OptionsView from "./options/OptionsView";

/** Companion trip page: full heat map + side-by-side comparison (the "link out" from chat). */
export default function TripPage({ tripId }: { tripId: string }) {
  // TODO: load this trip's options with apiFetch(`/trips/${tripId}/options`) instead of demo data.
  return (
    <TripProvider>
      <div className="min-h-dvh bg-[#f7f7f8]">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-line bg-white px-4 md:px-6">
          <Link href="/" aria-label="Back to chat"><ArrowLeft size={20} /></Link>
          <div className="leading-tight">
            <p className="text-sm font-semibold" data-trip-id={tripId}>weekend crew ☕ · Trip options</p>
            <p className="text-[11px] text-muted">New York City · Dec 18 – 21 · 4 people</p>
          </div>
        </header>
        <main className="mx-auto max-w-[1400px] p-4 md:p-6">
          <OptionsView wide />
        </main>
      </div>
    </TripProvider>
  );
}
