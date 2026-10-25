/** Presentation data only. The server/adapter must supply provider-backed fields. */
export type FallbackKind = "restaurant" | "stay" | "venue";
export type SpecialKind = "flight" | "train" | "concert" | "college_football";

export type CardImage = { src: string; alt: string };
export type CardAction = { label: string; url: string };
export type VerifiedStatus = {
  /** Complete label, such as "Open until 10 PM". Do not derive it from stale hours. */
  label: string;
  source: string;
  retrievedAt: string;
  verified: boolean;
};

export type FallbackCardData = {
  id: string;
  kind: FallbackKind;
  image: CardImage;
  title: string;
  rating?: number | null;
  reviewCount?: number | null;
  metadata: string[];
  status?: VerifiedStatus | null;
  chips?: string[];
  actions: CardAction[];
};

export type PriceChoice = {
  label: string;
  /** Formatted provider price; null means unknown. Never substitute a fabricated amount. */
  price: string | null;
};

export type SpecialCardData = {
  id: string;
  kind: SpecialKind;
  image: CardImage;
  title: string;
  subtitle: string;
  dateLabel: string;
  booking: CardAction;
  /** Travel cards have the ID of the current viewer only. Never list other members. */
  forViewerId?: string;
  originCode?: string;
  destinationCode?: string;
  choices?: PriceChoice[];
  provider: string;
  retrievedAt: string;
};

export type ViewerContext = {
  viewerId: string;
  locationPermission: "granted" | "denied" | "unavailable";
  /** Confirmed airport/station label supplied by the backend, never raw coordinates. */
  confirmedOrigin: string | null;
};

export type WidgetInput = {
  fallback: FallbackCardData | null;
  special?: SpecialCardData | null;
  viewer: ViewerContext;
};

export type WidgetSlide =
  | { kind: "fallback"; data: FallbackCardData }
  | { kind: "special"; data: SpecialCardData };

export type WidgetDeck = {
  slides: WidgetSlide[];
  reason: "special_plus_fallback" | "fallback_only" | "no_provider_result";
};
