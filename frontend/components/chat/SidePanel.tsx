"use client";

import { useTrip } from "@/lib/trip-context";
import PanelBody from "./PanelBody";

export default function SidePanel() {
  const { setPanelOpen } = useTrip();
  return (
    <div className="no-scrollbar h-full overflow-y-auto bg-white">
      <PanelBody onClose={() => setPanelOpen(false)} />
    </div>
  );
}
