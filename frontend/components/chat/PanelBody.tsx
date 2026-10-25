"use client";

import { useTrip } from "@/lib/trip-context";
import TripStart from "@/components/trip/TripStart";
import TripPanel from "@/components/trip/TripPanel";

export default function PanelBody({ onClose }: { onClose?: () => void }) {
  const { stage } = useTrip();
  return stage === "idle" ? <TripStart onClose={onClose} /> : <TripPanel onClose={onClose} />;
}
