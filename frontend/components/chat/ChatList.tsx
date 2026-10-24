import { Search, SquarePen } from "lucide-react";
import { CHATS } from "@/mocks/demo-data";
import { Avatar, GroupAvatar } from "./Avatar";

export default function ChatList({ activeId, onSelect }: { activeId: string; onSelect: (id: string) => void }) {
  return (
    <div className="flex h-full flex-col bg-white md:rounded-3xl md:border md:border-line md:p-3">
      <div className="flex items-center justify-between px-4 pb-2 pt-4 md:hidden">
        <h1 className="text-xl font-bold">Messages</h1>
        <SquarePen size={22} />
      </div>
      <label className="mx-4 flex h-10 items-center gap-2 rounded-xl bg-surface px-3 text-sm text-muted md:mx-0 md:h-9">
        <Search size={15} />
        <input className="w-full bg-transparent outline-none placeholder:text-muted" placeholder="Search chats" />
      </label>
      <p className="px-4 pb-2 pt-4 text-[10px] font-semibold tracking-wider text-muted md:px-1">CHATS</p>
      <ul className="no-scrollbar flex-1 space-y-2 overflow-y-auto px-2 md:px-0">
        {CHATS.map((c) => {
          const active = c.id === activeId;
          return (
            <li key={c.id}>
              <button
                onClick={() => onSelect(c.id)}
                className={`flex w-full items-center gap-3 rounded-2xl border px-3 py-2.5 text-left transition ${
                  active ? "border-violet-100 bg-violet-50/70" : "border-line bg-white hover:bg-surface"
                }`}
              >
                {c.group ? <GroupAvatar ids={c.members} size={40} /> : <Avatar id={c.members[0]} size={40} />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-semibold">{c.name}</span>
                  <span className="block truncate text-xs text-muted">{c.sub}</span>
                </span>
                {c.unread && (
                  <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1.5 text-[11px] font-semibold text-white">{c.unread}</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
