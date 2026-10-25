"use client";

import Link from "next/link";
import { MapPin, MessageCircle, type LucideIcon } from "lucide-react";
import { Avatar } from "./Avatar";

/** Product mark: our own logo, no Instagram or Meta branding. */
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <span className="flex items-center justify-center rounded-xl bg-brand text-white" style={{ width: size, height: size }}>
      <MapPin size={size * 0.48} />
    </span>
  );
}

function RailButton({ icon: Icon, label, active, badge, onClick }: { icon: LucideIcon; label: string; active?: boolean; badge?: number; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      title={label}
      className={`relative flex size-11 items-center justify-center rounded-xl transition hover:bg-surface ${active ? "text-foreground" : "text-muted hover:text-foreground"}`}
    >
      <Icon size={24} strokeWidth={active ? 2.25 : 1.75} />
      {!!badge && (
        <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold leading-none text-white ring-2 ring-white">{badge}</span>
      )}
    </button>
  );
}

/** Slim left rail (md and up): the way around the app. */
export default function NavRail({ unread, onMessages }: {
  unread: number; onMessages: () => void;
}) {
  return (
    <nav className="hidden w-[76px] shrink-0 flex-col items-center gap-1.5 border-r border-line bg-white py-5 md:flex" aria-label="Main">
      <div className="mb-4"><Logo /></div>
      <RailButton icon={MessageCircle} label="Messages" active badge={unread} onClick={onMessages} />
      <Link href="/login" aria-label="Account" title="Account" className="mt-auto rounded-full p-1 transition hover:bg-surface">
        <Avatar id="me" size={32} />
      </Link>
    </nav>
  );
}
