import { Image as ImageIcon } from "lucide-react";
import type { Message } from "@/lib/types";

/** One chat message: gradient bubble for you, gray for others, placeholder card for images. */
export default function MessageBubble({ m }: { m: Message }) {
  const mine = m.from === "me";
  if (m.kind === "image") {
    return (
      <div className="h-44 w-64 max-w-[75%] rounded-3xl bg-gradient-to-br from-amber-200 via-orange-300 to-stone-500 p-3 shadow-inner">
        <div className="flex h-full items-end rounded-2xl bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,.45),transparent_55%)] p-2 text-[11px] font-medium text-white/90">
          <ImageIcon size={14} className="mr-1" /> Juniper Coffee
        </div>
      </div>
    );
  }
  return (
    <div className={`max-w-[78%] whitespace-pre-line rounded-3xl px-4 py-2.5 text-[14px] leading-snug md:max-w-[70%] ${
      mine ? "brand-gradient text-white" : "bg-bubble text-foreground"}`}
    >
      {m.text}
    </div>
  );
}
