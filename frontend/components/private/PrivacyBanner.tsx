import { Lock } from "lucide-react";

/** Shown on every private surface so members always know what the group can and cannot see. */
export default function PrivacyBanner() {
  return (
    <p className="flex items-start gap-2 text-xs leading-snug text-muted">
      <Lock size={13} className="mt-px shrink-0" />
      Only you can see this. The group sees combined results, never your answers.
    </p>
  );
}
