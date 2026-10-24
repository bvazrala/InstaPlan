import { Suspense } from "react";
import TripPage from "@/components/trip/TripPage";

/** Full trip page: heat map + side-by-side comparison, linked from the trip card in chat. */
export default function Trip({ params }: PageProps<"/trip/[tripId]">) {
  // With cacheComponents on, params are runtime data and must be read inside Suspense.
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted">Loading trip…</div>}>
      {params.then(({ tripId }) => <TripPage tripId={tripId} />)}
    </Suspense>
  );
}
