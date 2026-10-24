import { MapPin, Phone, Search, Video } from "lucide-react";
import { GroupAvatar } from "./Avatar";

/** Product mark: our own logo, no Instagram or Meta branding. */
function Logo() {
  return (
    <span className="brand-gradient flex h-10 w-10 items-center justify-center rounded-xl text-white">
      <MapPin size={18} />
    </span>
  );
}

/** Desktop header (md and up). */
export default function TopBar() {
  return (
    <header className="hidden h-16 shrink-0 items-center gap-3 border-b border-line bg-white px-5 md:flex">
      <Logo />
      <div className="leading-tight">
        <p className="text-[15px] font-semibold">InstaPlan</p>
        <p className="text-[11px] text-muted">weekend crew ☕</p>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <label className="flex h-9 w-72 items-center gap-2 rounded-full border border-line bg-surface px-3 text-sm text-muted">
          <Search size={15} />
          <input className="w-full bg-transparent outline-none placeholder:text-muted" placeholder="Search messages" />
        </label>
        <button className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-white" aria-label="Video"><Video size={16} /></button>
        <button className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-white" aria-label="Call"><Phone size={16} /></button>
        <span className="flex h-9 items-center gap-2 rounded-full border border-line bg-white pl-1 pr-3 text-xs font-semibold">
          <GroupAvatar ids={["maya", "alex"]} size={28} /> weekend crew
        </span>
      </div>
    </header>
  );
}
