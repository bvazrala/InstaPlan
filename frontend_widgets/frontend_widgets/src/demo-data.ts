import type { FallbackCardData, SpecialCardData, WidgetInput } from "./widget-types";

/** Deliberately fictional presentation fixtures. Never publish these as live results. */
export const sampleFallbacks: FallbackCardData[] = [
  {
    id: "demo-restaurant", kind: "restaurant",
    image: { src: "/assets/restaurant-cabo-bobs.png", alt: "Burritos at Cabo Bob's" },
    title: "Cabo Bob's Burritos", rating: 4.6, reviewCount: 1200,
    metadata: ["$", "Mexican", "0.8 mi"],
    status: { label: "Open until 10 PM", source: "Presentation sample", retrievedAt: "sample", verified: false },
    chips: ["Burritos", "Bowls", "Vegan options"],
    actions: [{ label: "Call", url: "https://www.google.com/maps/search/?api=1&query=Cabo+Bobs+Burritos+Austin" }, { label: "Directions", url: "https://www.google.com/maps/search/?api=1&query=Cabo+Bobs+Burritos+Austin" }],
  },
  {
    id: "demo-stay", kind: "stay",
    image: { src: "/assets/stay-tokyo.png", alt: "Tokyo hotel skyline" },
    title: "Park Hyatt Tokyo", rating: 4.7, reviewCount: 3400,
    metadata: ["Hotel", "Shinjuku"],
    status: { label: "Open 24 hours", source: "Presentation sample", retrievedAt: "sample", verified: false },
    chips: ["Breakfast", "Pool", "Near station"],
    actions: [{ label: "Website", url: "https://www.hyatt.com/" }, { label: "Reserve", url: "https://www.google.com/travel/hotels" }],
  },
  {
    id: "demo-venue", kind: "venue",
    image: { src: "/assets/concert-moody-center.png", alt: "Concert crowd inside an arena" },
    title: "Moody Center", rating: 4.8, reviewCount: 8900,
    metadata: ["Arena", "Concerts", "1.4 mi"],
    status: { label: "Open until 11 PM", source: "Presentation sample", retrievedAt: "sample", verified: false },
    chips: ["Parking", "Accessible", "Clear bag"],
    actions: [{ label: "Tickets", url: "https://moodycenteratx.com/" }, { label: "Directions", url: "https://www.google.com/maps/search/?api=1&query=Moody+Center+Austin" }],
  },
];

export const sampleSpecials: SpecialCardData[] = [
  {
    id: "demo-flight", kind: "flight", image: { src: "/assets/travel-tokyo.png", alt: "Tokyo skyline at dusk" },
    title: "AUS → NRT", subtitle: "Austin → Tokyo Narita", dateLabel: "Apr 4–14 · Round trip · 1 stop",
    booking: { label: "Find flights", url: "https://www.google.com/travel/flights" },
    forViewerId: "demo-you", originCode: "AUS", destinationCode: "NRT",
    choices: [{ label: "Economy", price: "$1,120" }, { label: "Premium economy", price: "$1,680" }],
    provider: "Presentation sample", retrievedAt: "sample",
  },
  {
    id: "demo-train", kind: "train", image: { src: "/assets/travel-tokyo.png", alt: "Tokyo skyline at dusk" },
    title: "Kyoto → Tokyo", subtitle: "Kyoto Station → Tokyo Station", dateLabel: "Apr 8 · One way · Direct train",
    booking: { label: "Find train tickets", url: "https://smart-ex.jp/en/" },
    forViewerId: "demo-you", originCode: "Kyoto Station", destinationCode: "Tokyo Station",
    choices: [{ label: "Ordinary", price: "¥14,170" }, { label: "Green car", price: "¥19,040" }],
    provider: "Presentation sample", retrievedAt: "sample",
  },
  {
    id: "demo-concert", kind: "concert", image: { src: "/assets/concert-moody-center.png", alt: "Concert crowd inside an arena" },
    title: "Live at Moody Center", subtitle: "Moody Center · Austin, TX", dateLabel: "Apr 11 · Concert tickets",
    booking: { label: "Find concert tickets", url: "https://www.ticketmaster.com/search?q=Moody%20Center" },
    choices: [{ label: "Upper level", price: "$85" }, { label: "Floor", price: "$180" }],
    provider: "Presentation sample", retrievedAt: "sample",
  },
  {
    id: "demo-football", kind: "college_football", image: { src: "/assets/college-football-longhorns.png", alt: "Longhorns game and fireworks at night" },
    title: "Texas vs. Georgia", subtitle: "DKR–Texas Memorial Stadium · Austin", dateLabel: "Nov 14 · College football",
    booking: { label: "Find game tickets", url: "https://texaslonghorns.com/sports/football" },
    choices: [{ label: "Upper deck", price: "$95" }, { label: "Lower bowl", price: "$185" }],
    provider: "Presentation sample", retrievedAt: "sample",
  },
];

export const sampleInputs: WidgetInput[] = [
  { fallback: sampleFallbacks[1], special: sampleSpecials[0], viewer: { viewerId: "demo-you", locationPermission: "granted", confirmedOrigin: "AUS" } },
  { fallback: sampleFallbacks[1], special: sampleSpecials[1], viewer: { viewerId: "demo-you", locationPermission: "granted", confirmedOrigin: "Kyoto Station" } },
  { fallback: sampleFallbacks[2], special: sampleSpecials[2], viewer: { viewerId: "demo-you", locationPermission: "unavailable", confirmedOrigin: null } },
  { fallback: sampleFallbacks[2], special: sampleSpecials[3], viewer: { viewerId: "demo-you", locationPermission: "unavailable", confirmedOrigin: null } },
];
