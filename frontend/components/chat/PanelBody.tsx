"use client";

import { useTrip } from "@/lib/trip-context";
import MoreOptions from "./MoreOptions";
import TripPanel from "@/components/trip/TripPanel";

export default function PanelBody({ onClose }: { onClose?: () => void }) {
  const { stage } = useTrip();
  return stage === "idle" ? <MoreOptions onClose={onClose} /> : <TripPanel onClose={onClose} />;
}
