import { Lock } from "lucide-react";

/** Shown on every private surface so members always know what the group can and cannot see. */
export default function PrivacyBanner() {
  return (
    <div className="flex items-center gap-2 rounded-2xl bg-neutral-900 px-3.5 py-2.5 text-white">
      <Lock size={14} />
      <p className="text-xs leading-snug">Only you can see this. The group sees combined results, never your answers.</p>
    </div>
  );
}
