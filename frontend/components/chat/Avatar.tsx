/* eslint-disable @next/next/no-img-element -- Public avatar URLs are rendered directly with an initials fallback. */
import { memberById } from "@/mocks/demo-data";
import type { Chat, Member } from "@/lib/types";

const Dot = ({ size }: { size: number }) => (
  <span
    className="absolute bottom-0 right-0 rounded-full bg-emerald-500 ring-2 ring-white"
    style={{ width: Math.max(8, size * 0.24), height: Math.max(8, size * 0.24) }}
    aria-label="Active now"
  />
);

export function Avatar({ id, size = 36, ring = false, online = false, members }: { id: string; size?: number; ring?: boolean; online?: boolean; members?: Record<string, Member> }) {
  const m = members ? members[id] ?? { name: "Member", hue: 260,avatarUrl:null } : {...memberById(id),avatarUrl:null};
  return (
    <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      <span
        className={`relative flex h-full w-full items-center justify-center rounded-full font-semibold ${ring ? "ring-2 ring-white" : ""}`}
        style={{ fontSize: size * 0.4, background: `hsl(${m.hue} 70% 91%)`, color: `hsl(${m.hue} 50% 30%)` }}
        aria-label={m.name}
      >
        {m.name[0]}{'avatarUrl' in m && m.avatarUrl && /^(https?:\/\/|\/planner\/people\/)/.test(m.avatarUrl) && <img src={m.avatarUrl} alt={m.name} className="absolute inset-0 h-full w-full rounded-full object-cover" onError={event=>{event.currentTarget.style.display='none';}}/>}
      </span>
      {online && <Dot size={size} />}
    </span>
  );
}

/** Overlapping two-avatar group icon for group chats. */
export function GroupAvatar({ ids, size = 40, members }: { ids: string[]; size?: number; members?: Record<string, Member> }) {
  const s = size * 0.62;
  return (
    <span className="relative inline-block shrink-0" style={{ width: size, height: size }}>
      <span className="absolute left-0 top-0"><Avatar id={ids[0]} size={s} members={members} /></span>
      <span className="absolute bottom-0 right-0"><Avatar id={ids[1] ?? ids[0]} size={s} ring members={members} /></span>
    </span>
  );
}

/** Picks the right avatar for a chat: group pair or one friend. */
export function ChatAvatar({ chat, size = 40, online = false, members }: { chat: Chat; size?: number; online?: boolean; members?: Record<string, Member> }) {
  if (chat.group) return <GroupAvatar ids={chat.members} size={size} members={members} />;
  return <Avatar id={chat.members[0]} size={size} online={online} members={members} />;
}

/** Overlapping row of avatars, as in shadcn's avatar group. */
export function AvatarStack({ ids, size = 24 }: { ids: string[]; size?: number }) {
  return (
    <span className="flex -space-x-2">
      {ids.map((id) => <Avatar key={id} id={id} size={size} ring />)}
    </span>
  );
}
