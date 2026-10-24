"use client";

import { BarChart3, Bookmark, MapPin, PenLine, Sparkles, XCircle } from "lucide-react";
import { useTrip } from "@/lib/trip-context";

const ITEMS = [
  { icon: Bookmark, title: "Saved", sub: "Share saved places and notes" },
  { icon: MapPin, title: "Location", sub: "Share a place on the map" },
  { icon: BarChart3, title: "Poll", sub: "Vote on plans with the group" },
  { icon: PenLine, title: "Draw", sub: "Sketch a quick map or note" },
  { icon: Sparkles, title: "AI images", sub: "Generate images from a prompt" },
];

export default function MoreOptions({ onClose }: { onClose?: () => void }) {
  const { setStage } = useTrip();
  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[15px] font-semibold">More options</h2>
        <button onClick={onClose} aria-label="Close" className="text-foreground"><XCircle size={20} /></button>
      </div>

      <div className="mb-3 rounded-2xl border border-violet-100 bg-violet-50 p-3.5">
        <div className="flex items-start gap-3">
          <span className="brand-gradient flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white"><MapPin size={16} /></span>
          <div>
            <p className="text-[13px] font-semibold">Trip Planning</p>
            <p className="text-xs leading-snug text-muted">Plan routes, save stops, and share the itinerary with the group.</p>
          </div>
        </div>
        <button onClick={() => setStage("collecting")} className="brand-gradient mt-3 w-full rounded-xl py-2 text-sm font-semibold text-white">
          Start trip planning
        </button>
      </div>

      <ul className="space-y-2">
        {ITEMS.map(({ icon: Icon, title, sub }) => (
          <li key={title}>
            <button className="flex w-full items-center gap-3 rounded-2xl bg-surface px-3 py-2.5 text-left hover:bg-neutral-100">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-foreground"><Icon size={15} /></span>
              <span>
                <span className="block text-[13px] font-semibold">{title}</span>
                <span className="block text-[11px] text-muted">{sub}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
