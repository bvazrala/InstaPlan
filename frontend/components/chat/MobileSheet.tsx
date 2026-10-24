"use client";

import { useTrip } from "@/lib/trip-context";
import PanelBody from "./PanelBody";

/** Bottom sheet used below the lg breakpoint, where the side panel is hidden. */
export default function MobileSheet() {
  const { panelOpen, setPanelOpen } = useTrip();
  if (!panelOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center lg:hidden">
      <button aria-label="Close" className="absolute inset-0 bg-black/40" onClick={() => setPanelOpen(false)} />
      <div className="animate-sheet no-scrollbar relative max-h-[88dvh] w-full max-w-xl overflow-y-auto rounded-t-3xl bg-white pb-[env(safe-area-inset-bottom)] shadow-2xl">
        <div className="sticky top-0 z-10 flex justify-center bg-white pt-2"><span className="h-1 w-10 rounded-full bg-neutral-300" /></div>
        <PanelBody onClose={() => setPanelOpen(false)} />
      </div>
    </div>
  );
}
