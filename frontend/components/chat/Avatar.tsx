import { memberById } from "@/mocks/demo-data";

export function Avatar({ id, size = 36, ring = false }: { id: string; size?: number; ring?: boolean }) {
  const m = memberById(id);
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ${ring ? "ring-2 ring-white" : ""}`}
      style={{
        width: size, height: size, fontSize: size * 0.4,
        background: `linear-gradient(135deg, hsl(${m.hue} 70% 62%), hsl(${(m.hue + 40) % 360} 70% 45%))`,
      }}
      aria-label={m.name}
    >
      {m.name[0]}
    </span>
  );
}

/** Overlapping two-avatar group icon for group chats. */
export function GroupAvatar({ ids, size = 40 }: { ids: string[]; size?: number }) {
  const s = size * 0.68;
  return (
    <span className="relative inline-block shrink-0" style={{ width: size, height: size }}>
      <span className="absolute left-0 top-0"><Avatar id={ids[0]} size={s} ring /></span>
      <span className="absolute bottom-0 right-0"><Avatar id={ids[1] ?? ids[0]} size={s} ring /></span>
    </span>
  );
}
