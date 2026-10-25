import { CornerUpLeft, Heart, MapPin, MoreHorizontal, Smile } from "lucide-react";
import type { Message } from "@/lib/types";

export type BubblePos = "single" | "first" | "middle" | "last";

// Corners next to the previous or next bubble from the same sender are tightened, as in Instagram and iMessage.
const CORNERS = {
  mine: { single: "", first: "rounded-br-md", middle: "rounded-r-md", last: "rounded-tr-md" },
  theirs: { single: "", first: "rounded-bl-md", middle: "rounded-l-md", last: "rounded-tl-md" },
};

/** One chat message: solid accent bubble for you, gray for others, place card for shared spots. Double-click to react. */
export default function MessageBubble({
  m, pos = "single", reacted = false, onReact, onReply,
}: { m: Message; pos?: BubblePos; reacted?: boolean; onReact?: () => void; onReply?: () => void }) {
  const mine = m.from === "me";
  const corners = CORNERS[mine ? "mine" : "theirs"][pos];

  const body =
    m.kind === "image" ? (
      <div className="relative h-56 w-48 overflow-hidden rounded-[22px] bg-gradient-to-br from-amber-100 via-orange-200 to-stone-400 md:w-56">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_25%,rgba(255,255,255,.5),transparent_55%)]" />
        <div className="absolute inset-x-0 bottom-0 flex items-center gap-1.5 bg-gradient-to-t from-black/45 to-transparent px-3 pb-2.5 pt-8 text-[12px] font-medium text-white">
          <MapPin size={13} /> {m.caption ?? "Juniper Coffee"}
        </div>
      </div>
    ) : (
      <div
        className={`whitespace-pre-line rounded-[22px] px-3.5 py-2 text-[15px] leading-[1.35] ${corners} ${
          mine ? "bg-brand text-white" : "bg-bubble text-foreground"}`}
      >
        {m.text}
      </div>
    );

  return (
    <div className={`group flex max-w-[78%] items-center gap-1.5 md:max-w-[68%] ${mine ? "flex-row-reverse" : ""}`}>
      <div className={`relative ${reacted ? "mb-3" : ""}`} onDoubleClick={onReact}>
        {body}
        {reacted && (
          <span className={`absolute -bottom-3 flex h-6 min-w-6 items-center justify-center rounded-full bg-white px-1 shadow-[0_0_0_1.5px_#fff,0_1px_3px_rgba(0,0,0,.18)] ${mine ? "right-2" : "left-2"}`}>
            <Heart size={13} className="fill-rose-500 text-rose-500" />
          </span>
        )}
      </div>
      {onReact && (
        <div className="hidden shrink-0 items-center text-muted opacity-0 transition focus-within:opacity-100 group-hover:opacity-100 md:flex">
          <button onClick={onReact} aria-label={reacted ? "Remove reaction" : "React"} className="flex size-7 items-center justify-center rounded-full hover:bg-surface hover:text-foreground"><Smile size={16} /></button>
          {onReply && <button onClick={onReply} aria-label="Reply" className="flex size-7 items-center justify-center rounded-full hover:bg-surface hover:text-foreground"><CornerUpLeft size={16} /></button>}
          <button aria-label="More" className="flex size-7 items-center justify-center rounded-full hover:bg-surface hover:text-foreground"><MoreHorizontal size={16} /></button>
        </div>
      )}
    </div>
  );
}
