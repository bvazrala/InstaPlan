import type { CardAction, SpecialCardData, WidgetDeck, WidgetInput } from "./widget-types";

const ALLOWED_KINDS = new Set(["flight", "train", "concert", "college_football"]);
const TRAVEL_KINDS = new Set(["flight", "train"]);

/** Only open http(s) provider links; an absent/unsafe link never becomes a button. */
export function safeExternalUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return (url.protocol === "https:" || url.protocol === "http:") && !url.username && !url.password && ![...url.searchParams.keys()].some(key => ["api_key","access_token","key"].includes(key.toLowerCase())) ? url.toString() : null;
  } catch {
    return null;
  }
}

export function safeAction(action: CardAction | null | undefined): CardAction | null {
  const url = safeExternalUrl(action?.url);
  return url && action?.label.trim() ? { label: action.label.trim(), url } : null;
}

function specialIsReady(special: SpecialCardData, input: WidgetInput): boolean {
  if (!ALLOWED_KINDS.has(special.kind) || !special.title.trim() || !special.dateLabel.trim()) return false;
  if (!safeExternalUrl(special.image.src) || !safeAction(special.booking) || !special.provider.trim() || !Number.isFinite(Date.parse(special.retrievedAt))) return false;
  if (!TRAVEL_KINDS.has(special.kind)) return true;

  // A viewer with location disabled/unavailable gets only the place card. A
  // device coordinate must not be treated as a confirmed airport or station.
  const { viewer } = input;
  return viewer.locationPermission === "granted"
    && Boolean(viewer.confirmedOrigin?.trim())
    && special.forViewerId === viewer.viewerId
    && special.originCode?.trim().toUpperCase() === viewer.confirmedOrigin?.trim().toUpperCase()
    && Boolean(special.destinationCode?.trim());
}

/** One widget, at most two slides. Keep all routing decisions out of the JSX. */
export function selectWidgetDeck(input: WidgetInput): WidgetDeck {
  if (!input.fallback) return { slides: [], reason: "no_provider_result" };
  const fallback = { kind: "fallback" as const, data: input.fallback };
  if (!input.special || !specialIsReady(input.special, input)) {
    return { slides: [fallback], reason: "fallback_only" };
  }
  return {
    slides: [{ kind: "special", data: input.special }, fallback],
    reason: "special_plus_fallback",
  };
}
