# InstaPlan widget handoff

This folder is a standalone, runnable UI and animation handoff for the HackTX demo. It is **outside the InstaPlan repository**. The repository was read at local `refactor/app` commit `1cbdea4` and was not pulled or edited. The working tree already had an unrelated untracked `backend/scripts/listening_lab/.cache/`; this handoff did not touch it.

## What to open

Run `npm install` and `npm run dev` from this folder, then open `http://localhost:3000`. The preview shows four special cards, three cards using one common fallback design, and a denied-location example. **Replay formation** shows the loading shimmer and staged reveal. The Figma source is [the design board](https://www.figma.com/design/AFvnsv7xTWnRyzUxQjkQgP/Untitled?node-id=4-271) and [the native Motion preview](https://www.figma.com/design/AFvnsv7xTWnRyzUxQjkQgP/Untitled?node-id=8-72). The component lives in `src/PlanWidget.tsx`, its styles and animation in `src/PlanWidget.css`, and the pure selection logic in `src/widget-rules.ts`.

## Hackathon product rules

| Decision | Rule |
| --- | --- |
| Container | One widget per plan in the group chat, fixed 338 × 354 design slot, up to two slides. Swipe vertically, click dots or use arrow keys to switch. Do not move the chat layout while forming. |
| Shared fallback | A photo-led place card for restaurant, stay or venue with the **same layout**: category, title, provider rating and review count if known, compact metadata, green open-status line if verified, up to three supported chips, and up to two relevant actions. It also gets the formation animation. |
| Special cards | Only **flight**, **train**, **concert** and **college football**. Flight only and train only; no hybrid itineraries, buses, drives, other sports or generic events. Unsupported cases use the fallback. |
| Slide order | When a supported special card has all required evidence: special first, corresponding fallback second. Otherwise one fallback. Never more than two. |
| Travel privacy | The travel card describes **only the viewing person’s** route. Do not display other travelers’ origins or a “departing from” group list. No location permission, missing/disabled location, absent confirmed origin, unmatched viewer ID, or absent destination means fallback. Location access alone cannot choose an airport or station; a confirmed origin is still required. |
| Choice tiers | Cheaper and premium fare/seat/ticket tiers can appear when sourced. If one or both prices are missing, show an unpriced comparison prompt rather than inventing a number. No personalized budget statement. |
| Action | A safe HTTP(S) provider listing or booking URL. No hardcoded sample provider search link in production. If a special booking URL is absent, route to fallback. |

The fallback remains useful even when all special sourcing fails. It does **not** claim that an unknown venue is open. The green line is conditional, and its text must come from fresh, verified operating-hours data. A hotel or stadium may have no meaningful “Open until …” time; hide the line in that case. The preview deliberately supplies **fictional, unverified** status examples for all three categories so a designer can see the shared position and green treatment. They render only because the gallery passes `demo`; production must omit that flag.

## Fields that must be earned by data

Do not invent event dates, ticket prices, flight or train fares, operating hours, reviews, dietary/accessibility fit, cancellation deadlines, group budgets, or live availability. In particular, remove the older concepts “works for the whole group,” “under everyone’s budget,” “free cancellation until Mar 20,” and unsourced “doors open” claims. The sample card titles and matchups in `src/demo-data.ts` are presentation fixtures, not real search results. A search result timestamp is not proof that opening hours are currently valid. `PlanWidget` only displays a green status in production when its `verified` flag, source, and timestamp are present and the timestamp is at most 15 minutes old; the backend should also confirm the local venue time zone and open state before setting that flag.

The five photos in `public/assets` are discrete images exported from the Figma file. The Longhorns photo is the image supplied by the project owner. Every photo uses `object-fit: cover`, preserving aspect ratio and cropping inside its frame; nothing stretches. Replace sample images with licensed/provider imagery as appropriate for production. SVG star and stack-dot assets are also local. No temporary Figma asset URL is used at runtime.

## Animation contract

The Figma reference timeline is 3.2 seconds; the useful formation finishes around 2.2 seconds. The production CSS runs **once** when a result arrives, then rests. Figma’s exported `motion.dev` snippets in `design-reference/figma-motion-source.json` specify `repeat: Infinity` because the design timeline loops in Figma; do **not** carry that repeat into the chat UI.

| Phase | Approximate time | Behavior |
| --- | --- | --- |
| Waiting | Until sourced result | Full-size pearl skeleton; light travels across it in a soft shimmer. |
| Card appears | 0–350 ms | Card settles upward 8 px, with restrained ease; card size stays fixed. |
| Photo and category | 850–1,550 ms | Image becomes sharp from 14 px blur with a 1.025 → 1 scale; category arrives gently. |
| Content | 1,150–2,120 ms | Title, metadata, two price choices and booking action rise 5–7 px in sequence. |
| Rest | After ~2.2 s | Fully readable and still. No bounce or indefinite shimmer. |

The same animation applies to a fallback card. `prefers-reduced-motion` removes movement. Keep a stable 338 × 354 slot (or scale the whole card responsively) to prevent chat jumps. The `animationKey` prop restarts the reveal when a new recommendation is published; `loading` keeps the skeleton visible while a provider request is active.

## Branch context read for the adapter

The current chat UI is the **Next.js 16 / React 19** app at `frontend/components/chat/ChatThread.tsx`, inside `AppShell.tsx`. The older plain `backend/scripts/listening_lab/static` HTML/CSS/JS was not used. The thread currently renders `PlannerApprovalCard` and a compact planner card in the message area. The proposed widget should be mounted near that planner result when a ready recommendation arrives; this folder intentionally does not change that integration point.

`frontend/components/planner/PlannerRecommendations.tsx` currently renders travel `Option` results and venue results. `frontend/lib/types.ts` and `docs/api-contract.md` define the public planner contract. `backend/app/integrations/serpapi_normalized.py` preserves provider evidence; `VenueOut` currently has rating, price level, safe URL, provider and retrieval time, but **does not expose photo, operating-hours status or event ticket fields**. The existing travel `Option` supports `Flight` and `Drive`, not train. Concert and college football ticket inventory are also not present in the current public contract. An adapter/backend extension must supply those fields before the special cards or green status can be live. Do not turn the design fixtures into production defaults.

`Planner` contains `recommendations.kind: "travel" | "venues"` and is refreshed after `planner.updated` / `options.ready`. The branch has a private origin route, and `where.origins` carries coarse confirmed labels. Precise `originLocation` belongs to the current user’s encrypted private preferences. The widget receives only a **per-viewer confirmed airport/station code or label**, never raw coordinates and never another member’s private data. Group responses must not include budgets, check-in answers or other private values. The backend’s existing `AGENTS.md` privacy rules continue to govern integration.

## Integration order for the other agent

1. Add a server-side adapter that produces `FallbackCardData` from a real venue/place result. Map nullable rating, provider URL and metadata faithfully. Add a provider-backed image and opening-hours summary only when available.
2. Add special candidates only for the four allowed kinds. A train or event candidate needs a **new provider feed and explicit public API shape**; the present branch does not have one. Flight data should be per-viewer and use the confirmed origin plus a valid listing URL.
3. Pass `{ fallback, special, viewer }` through `selectWidgetDeck()`; render `<PlanWidget deck={deck} loading={active} animationKey={generation.runId ?? ""} />`. Never pass `demo` in production.
4. Mount the component where the current planner result appears in `ChatThread.tsx` or its planner child, after ensuring only data intended for that viewer enters props. Retain the existing chat and planner behavior.
5. Recheck repo `AGENTS.md`, API contract, lint/build and privacy tests when integrating. This handoff was intentionally kept outside the repo.

## Files

| Path | Purpose |
| --- | --- |
| `src/widget-types.ts` | Standalone data shape for a widget. |
| `src/widget-rules.ts` | Evidence gate and one/two-slide decision. |
| `src/PlanWidget.tsx` | Reusable interactive React UI. |
| `src/PlanWidget.css` | Styles and one-shot formation motion. |
| `src/demo-data.ts` | Explicitly fictional gallery fixtures. |
| `app/` | Standalone Next.js preview; can be discarded after integration. |
| `public/assets/` | Local image and SVG design assets. |
| `design-reference/figma-motion-source.json` | Figma’s authoritative animated-node inventory and snippets. |
| `design-reference/motion-spec.json` | Compact timing and behavior contract. |

### Source and verification

- Figma design: <https://www.figma.com/design/AFvnsv7xTWnRyzUxQjkQgP/Untitled?node-id=4-271>
- Figma Motion: <https://www.figma.com/design/AFvnsv7xTWnRyzUxQjkQgP/Untitled?node-id=8-72>
- Repo branch inspected locally: `refactor/app` at `1cbdea4`; no pull or checkout occurred.
