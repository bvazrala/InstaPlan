# API contract

The agreement between `frontend/` and `backend/`. Change it, `backend/app/schemas.py` and `frontend/lib/types.ts` in the same PR.

- **Base URL:** `NEXT_PUBLIC_API_URL` (local: `http://localhost:8000`). Live docs: `/docs`.
- **Auth:** every REST call sends `Authorization: Bearer <Supabase access token>`; `lib/api.ts` adds it.
- **JSON:** camelCase.
- **Errors:** `401` no or bad token; `404` not found *or not a member* (the API never confirms what exists to outsiders); `409` wrong trip stage; `501` not built yet.

## REST

### Group-visible (any member of the chat)

| Method | Path | Body | Returns | Req |
| --- | --- | --- | --- | --- |
| GET | `/chats` | | `Chat[]` | R21 |
| GET | `/chats/{chatId}/members` | | `Member[]` | R21 |
| GET | `/chats/{chatId}/messages` | | `Message[]` | R21 |
| POST | `/chats/{chatId}/messages` | `{ text }` | `Message` | R21 |
| POST | `/chats/{chatId}/trips` | | `Trip` | R1 |
| GET | `/chats/{chatId}/trips/active` | | `Trip or null` | R12 |
| GET | `/trips/{tripId}` | | `Trip` | |
| POST | `/trips/{tripId}/stage` | `{ stage }` | `Trip` | |
| GET | `/trips/{tripId}/facts` | | `Fact[]` | R3, R4 |
| PATCH | `/trips/{tripId}/facts/{factId}` | `{ value }` | `Fact` | R5 |
| DELETE | `/trips/{tripId}/facts/{factId}` | | 204 | R5 |
| POST | `/trips/{tripId}/vote` | `{ going }` | `Trip` | R8 |
| GET | `/trips/{tripId}/options` | | `Option[]` | R12–R14 |
| POST | `/trips/{tripId}/options/generate` | optional `{ inputs: PlanningInput }` | 202 `Generation` | R12 |
| GET | `/trips/{tripId}/options/status` | | `Generation` | R12 |
| POST | `/trips/{tripId}/pick` | `{ optionId, acknowledgeCapacity?: boolean }` | `Trip` | R15 |
| GET | `/trips/{tripId}/expenses` | | `Expense[]` | R17 |
| POST | `/trips/{tripId}/expenses` | `{ description, amount }` | `Expense` | R17 |
| GET | `/trips/{tripId}/transfers` | | `Transfer[]` | R17 |
| POST | `/trips/{tripId}/transfers/pay` | `{ to, amount }` | `Transfer[]` | R17 |

### Owner only (always the logged-in user; no user id in any path)

| Method | Path | Body | Returns | Req |
| --- | --- | --- | --- | --- |
| GET | `/trips/{tripId}/me/private` | | `PrivatePrefs` | R9 |
| PUT | `/trips/{tripId}/me/private` | `PrivatePrefs` | `PrivatePrefs` | R9 |
| DELETE | `/trips/{tripId}/me/private` | | 204 | R9 |
| GET | `/trips/{tripId}/me/checkin` | | `CheckInMessage[]` | R9, R22 |
| POST | `/trips/{tripId}/me/checkin` | `{ text }` | `CheckInMessage[]` | R9, R22 |
| GET | `/trips/{tripId}/me/budget-suggestion` | | `{ amount, reason }` | R11 |

## WebSocket

`ws(s)://<api>/ws/chats/{chatId}`, one per open chat (`lib/socket.ts`).

1. Connect, then send `{ "type": "auth", "token": "<access token>" }` as the first message within 10 seconds. The token is never put in the URL.
2. Non-members and bad tokens are disconnected with code 1008.
3. Send chat messages with `{ "type": "message.send", "text": "..." }`.
4. After authentication and membership checks, the server sends `chat.ready`. Fetch messages then to close the gap between initial load and joining the live channel.

**Server → client events.** Group events go to everyone in the chat. `private.*` events go only to their owner's connections.

| Event | Payload | Sent to |
| --- | --- | --- |
| `chat.ready` | `{}` | this connection |
| `message.new` | `{ message: Message }` | chat |
| `trip.offer` | `{ chatId }` | chat |
| `trip.stage` | `{ tripId, stage }` | chat |
| `fact.updated` | `{ tripId, fact: Fact }` | chat |
| `options.ready` | `{ tripId }` (then GET the options) | chat |
| `private.checkin` | `{ tripId, message: Message }` | owner only |

## Shapes

```ts
type Message  = { id: string; from: string /* user id or "assistant" */; kind: "text"; text: string; sentAt: string };
type Trip     = { id: string; chatId: string; stage: Stage; pickedOptionId: string | null;
                  yesVotes: number; memberCount: number; checkinsDone: number /* a count, never who */ };
type Fact     = { id: string; field: string; value: string; by: string | null; src: string | null; required: boolean };
type Option   = { id: string; title: string; place: string; dates: string; nights: number; lodging: string;
                  lodgingShare: number; daily: number; fit: number; certainty: string; cats: Record<Category, number | null>;
                  fairestRank: number /* never the burden ratio */; people: TravelLeg[]; hue: number;
                  listingUrl?: string | null; pricedAt?: string | null;
                  currency: string; groupTotal: number | null; lodgingTotal: number | null;
                  maxTravelHours: number | null; durationBasis: "round_trip";
                  priceCoverage: "quoted_with_taxes" | "estimated_before_taxes" | "missing" | "unknown";
                  feasibility: "feasible" | "unverified" | "infeasible"; pickEligible: boolean;
                  capacityAckRequired: boolean; warnings: string[]; costScope: "flights_and_lodging" };
type TravelLeg = { id: string; origin: string; mode: "Flight" | "Drive";
                   hours: number | null; cost: number | null;
                   lodgingAllocation?: number | null; subtotal?: number | null };
type PlanningInput = { destinations: {name: string; airports: string[]; sourceFactIds?: string[]}[];
                      checkin?: string | null; checkout?: string | null; origins?: Record<string, string> };
type Generation = { status: "idle" | "resolving" | "generating" | "needs_input" | "ready" | "failed";
                    runId: string | null; message: string | null; missing: string[];
                    inputs: PlanningInput | null; partial: boolean; optionCount: number };
type PrivatePrefs = { budgetCap: number | null; dietary: string[]; accessibility: string[]; noGos: string;
                      privateScores: Record<string, number> /* -2..+2 */ };
type Stage    = "collecting" | "voting" | "checkin" | "options" | "picked" | "settle";
```

The frontend `Stage` adds `"idle"` for "no trip yet".

## Live option generation

Generation is allowed during `checkin` and `options`. A POST returns 202 immediately;
poll status while work runs. Requests reuse an active run for at most five minutes.
A stale run appears failed and can be retried. The default total HTTP request limit
is 100 (including retries), concurrency is four, and provider work stops scheduling
after 270 seconds. A restarted process does not automatically resume a lost run.

`needs_input` returns missing public search fields and the public resolved inputs.
Correct dates, destinations or participant airport codes by resubmitting `inputs`.
Corrections do not replace server-side hard constraints or preference scores. They
are retained for subsequent searches while the input revision remains unchanged.
No private preferences, private revisions, rejected-member reasons or budgets are
included in public inputs/status. Underlying private changes invalidate old options
without explaining which member or value changed.

Successful publication atomically replaces options and changes the trip to `options`.
An empty successful search is `ready` with optionCount zero. Provider failure preserves
the previous options. Partial success is `ready` with partial=true. `options.ready`
is emitted only after commit; refresh on reconnect/focus and poll as a fallback.

`groupTotal` is the authoritative flights-plus-shared-lodging subtotal. Individual
`lodgingAllocation` values sum to `lodgingTotal` exactly, including remainder cents;
`subtotal` is the authoritative individual flight-plus-lodging amount. `lodgingShare`
is a legacy average only. `daily` is zero for this flow: meals, activities and ground
travel are excluded, not priced at zero. All live hours are ROUND-TRIP elapsed hours,
including layovers. Unknown measurements remain null. `pricedAt` comes from provider
retrieval times, never option insertion time. Category scores without evidence for
an offered component (Food and Activities) are null and displayed as not evaluated.

All four sorts apply to the same filtered set. Balanced min-max normalizes group
cost and maximum round-trip duration, with weight 0.5 by default (0=time, 1=cost).
Ties use option IDs. Fairest minimizes the largest burden against submitted ceilings,
then group cost, then ID. Only a fairest ordinal leaves the server. Missing ceilings
are unconstrained, zero ceilings reject positive costs, and groups smaller than three
ignore private budgets entirely. Without eligible budgets Fairest falls back to cheapest.

A capacity-only uncertainty is selectable when pickEligible=true and the pick request
includes acknowledgeCapacity=true. Other unverified hard requirements cannot be
acknowledged away. Known conflicts are excluded. The server also rejects picking
while a run is active or when the published inputs have changed. Picking persists
the option and transitions to `picked`; explicitly return to `options` before
regenerating. Existing saved/fixture option fields remain readable, but older options
without verification metadata require regeneration before selection.

The generation-state table is new and created by normal application startup, with
the same RLS lockdown as every other table. No existing tables are dropped or altered.


## Explicit local demo sessions

`DEMO_MODE=true` with `APP_ENV=dev` selects the isolated local SQLite demo database
and seeds synthetic group members plus a ready-to-price trip on startup. This mode
never connects to the configured PostgreSQL database and does not create Supabase
Auth users. Normal authentication remains the default when the flag is absent/false.

`GET /health` additionally returns `demoMode: boolean` and `demoUserId: string | null`.
A frontend on localhost/127.0.0.1 with a local backend uses this declaration to select
the fixed `demo-you` identity. REST requests and the first WebSocket message still
carry a bearer token (`instaplan-local-demo`, a public development marker, not a secret).
This token is rejected when demo mode is disabled. The caller cannot choose another
user ID. Demo HTTP/WebSocket access is restricted to loopback clients and trusted
browser origins; all membership and private-owner checks continue to apply.
The UI visibly labels the local demo. Refresh the browser after changing modes.

## Unified planner (Dining, Travel, Entertainment)

New chats start with **+ → Planner**. Creation needs a title, topic and browser IANA timezone; location is optional. An initiator has no ownership privilege. Existing travel endpoints remain available for legacy trips; unified planners use these routes instead. Every operation checks current chat/trip membership.

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| POST | `/chats/{chatId}/planners` | `{title, topic, location?, timezone}` | 201 `Planner` |
| GET | `/chats/{chatId}/planner` | | latest `Planner` or null |
| GET | `/trips/{tripId}/planner` | | `Planner` |
| PATCH | `/trips/{tripId}/planner` | `{revision, field, value, demoSpeakerId?}` | `Planner` |
| POST | `/trips/{tripId}/planner/approve` | `{revision: approvalRevision, approve, demoSpeakerId?}` | `Planner` |
| POST | `/trips/{tripId}/planner/revise` | | `Planner` |
| POST | `/trips/{tripId}/planner/retry` | | 202 `Planner` |
| POST | `/trips/{tripId}/planner/pricing` | `{inputs: PlanningInput}` | 202 `Planner` |
| POST | `/trips/{tripId}/planner/places` | `{query, sessionToken}` | `[{id,label}]` |
| POST | `/trips/{tripId}/planner/destination` | `{revision, placeId, sessionToken}` | `Planner` |
| POST | `/trips/{tripId}/planner/pick` | `{optionId, acknowledgeCapacity?}` | `Planner` |
| PUT | `/trips/{tripId}/me/origin` | `{latitude, longitude, label}` | `{label}` (owner only) |

`Planner` contains `tripId`, `title`, `topic`, `timezone`, optimistic `revision`, `approvalRevision`, `status` (`collecting`, `approved`, `picked`), typed `template`, effective `attendance`, `poll`, `listening`, `missing`, `generation`, `recommendations`, `pricedMembers`, `pickedId`, and `provenance` (public source-message ID → public speaker ID). It contains no internal notes, prompts, traces, model metrics or private assessments.

`template` contains `when: {flexibility, agreed}`, `where: {destination, destinationHint, searchArea, origins}`, `preferences`, `hardConstraints`, `cluster`, `sources`, title and topic. Member maps use actual member IDs. Explicit flexible availability is `null` **with the member key present**; an absent key means missing. An agreed time is `{label,date}`; unresolved dates remain null. `where.origins` is a coarse, manually supplied city or confirmed airport label, never device coordinates. `sources` values are message IDs, `manual`, or `suggested`. Origins are omitted from listener model context. Topic cluster fields retain their extraction names: Dining `meal_type,cuisine`; Travel `trip_type,accommodation`; Entertainment `activity_type`.

Editable field paths: `when.agreed`, `when.flexibility`, `where.search_area`, `where.origins`, `attendance`, `preferences`, `hard_constraints`, the active topic's cluster fields, and `threshold`. Personal edits apply to the caller. `demoSpeakerId` is allowed only for public messages/edits/votes in the loopback-only four-person demo chat. It never selects a private identity, including when passed to an owner-only route.

`poll` contains `eligible`, `approvals`, `changes`, `required`, `threshold`, `ready`. Eligible voters include conditional members and exclude explicit declines. Speaking implies going unless explicit attendance overrides it; silent members remain conditional. Readiness requires a location and availability from going members, or agreed timing. Optional topic fields never block readiness. Voting waits until queued listening finishes. Thresholds are 0.4, 0.5, 0.6, default 0.5; required approvals are `max(1, ceil(threshold * eligible.length))`. A change vote never declines attendance. Meaningful criteria, explicit attendance, membership and threshold changes invalidate votes; provenance, processing, notes and speaking alone do not. Approval freezes criteria and going-member pricing roster. Exact flight dates and airports can be confirmed afterward without inventing them; changed destination or an agreed exact date requires revision.

`listening` is `idle`, `queued`, `listening`, or `failed`. Batches are durable, debounced 900 ms, contain at most six source messages and use four preceding/two following context messages. Only batch messages support changes. Manual edits win against older sources; obsolete epochs cannot apply. Interrupted leases are recovered after 90 seconds. Retry requeues failed work. Suggested topic values only fill empty fields and yield to explicit corrections.

`recommendations` is discriminated by `kind`: `{kind:"travel", options: Option[]}` reuses the existing exact-cost travel contract; `{kind:"venues", venues: Venue[]}` carries venue identity, title, address, provider-supported rating, nullable `priceLevel`, nullable safe link, provider, retrieval time, nullable aggregate public `fit`, evidence, warnings, and `pickEligible`. Venue price levels are not dollar amounts. Future opening hours, exact costs, tickets, dietary/accessibility suitability remain unknown unless supported. Unverified hard requirements block server-side picking. Venue fit uses only provider-reported names/categories and public preferences; unknown fit remains null. Venue order is fit/rating with stable IDs; travel retains all four cost/time/fairness sorts.

Generation uses the existing five-minute lease and atomic publication, bound to the approved revision, frozen participants, actual membership, confirmed pricing inputs and an opaque private revision. Errors preserve prior rows/results; successful empty searches publish an empty set. Picking is blocked while a generation is active or approval is invalid. Unknown lodging capacity requires explicit acknowledgment; other unverified hard requirements cannot be acknowledged away.

`planner.updated` events carry only `{type,tripId}`; clients refetch snapshots. `options.ready` is emitted only after publication commits. Clients poll every 1.5 seconds and refresh on reconnect/online. Ordinary public messages continue after approval without changing frozen criteria. Revise reopens listening and requires approval before replacement recommendations. No group option stores private ceilings or burden ratios.

Precise coordinates live only in the caller's encrypted `PrivatePrefs.originLocation`, read through `/me/private`. The public origin endpoint response contains only the coarse label. Device coordinates never become a flight airport. Public demo perspectives do not change `/me/` authentication.

Provider configuration: `MUSE_API_KEY` for listening, `SERPAPI_KEY` for live recommendations, optional server-only `GOOGLE_MAPS_API_KEY` for the exact Places picker. Missing keys yield explicit unavailable/retry states; no fabricated recommendations or model output. Places Autocomplete uses session tokens and explicit field masks, followed by human-confirmed Place Details. Paid provider smoke checks remain opt-in. The standalone listening lab is unchanged and retains its separate diagnostics.

Confirmed initial plans use the existing parent trip's `confirmed` stage while recommendation inputs resolve; this is distinct from the planner's public `approved` status. A failed refresh can still display and pick a previously published result when its approved revision and all input fingerprints remain current.

## Planner presentation and recommendation widgets

The default planner is a public read-only summary of title, destination, timing, going/conditional participants, and topic details. Corrections live behind **Edit details**. Creation only asks for a title and topic; location is optional. Creation leaves the conversation visible. Approval leaves a persistent **Plan confirmed** summary in the chat and opens the recommendation phase below it. Private check-in is a separate collapsed owner-only surface. Revision invalidates the confirmed summary and requires reapproval.

The integrated widget source is `frontend/components/planner/widgets/`, adapted from the supplied `frontend_widgets` handoff. Gallery fixtures, fictional status labels, sample travel photos and global gallery styles are not production defaults. The component reserves a 338 × 354 slot, reveals once per publication, respects reduced motion, and supports up to two slides with keyboard, dots and vertical swiping.

Public venue additions are optional `imageUrl`, `reviewCount`, `category`, and `special`. `special` carries sourced event identity, `kind` (`concert` or `college_football` from the live adapter), image, title, subtitle, `dateLabel`, a safe provider `booking` action, empty/quoted `choices`, provider and `retrievedAt`. Google Maps provides venue imagery/reviews. An Entertainment plan explicitly requesting concerts or college football can make one additional cached, bounded Google Events search. The event must match the recommended venue and have a provider image, date label and ticket URL. Ambiguous provider month/day labels do not prove an approved exact date. Failed optional event searches preserve the venue suggestion. Ticket availability/prices remain unknown; no ticket tiers are invented.

Travel `Option` adds optional `imageUrl`, `lodgingRating`, `lodgingReviewCount`, and `lodgingAmenities`, preserving older fixtures. These map from the exact lodging result and survive group aggregation; review count is never occupancy. Place cards never infer a verified green open-status line from search retrieval time. No fresh verified local opening-hours feed is currently exposed, so that line stays hidden.

`POST /trips/{tripId}/me/widget/flight` takes `{optionId, locationGranted}` and returns `{special: WidgetSpecial|null}`. Membership and the authenticated owner determine the itinerary; no caller-selected user ID is accepted. The browser asks for location permission only after **Show my flight card**; it does not send coordinates to this endpoint. An explicitly confirmed origin is still required, and permission never chooses an airport. The service checks the current approved/published revision before and after an optional token-bound Google Flights booking-options request. Unsafe links and POST-only bookings are not turned into GET buttons. Provider tokens remain in the RLS-protected server-only `WidgetItinerary` table, published atomically with options; group snapshots, events and widgets never expose them.

Flight cards show only the authenticated viewer's route and fall back to the sourced stay when permission, confirmed origin, provider imagery or a safe booking action is unavailable. Demo public perspective changes never change the private widget viewer. The reusable train renderer is available behind the same evidence gate; no train provider is configured, so no live train fare or itinerary is fabricated. Only flight, train, concert and college football can use a special slide. Other activities/sports use the common place card.

## Conversation-only hackathon demo (current default)

New `PlannerCreate` requests default to `flow: "conversation"`. `flow: "legacy"` retains the older approval/private-evaluation behavior for historical clients and engine tests. The normal frontend uses the conversation flow and has no private check-in, bank linking, comparison/sort, expense or settlement step.

Creation optionally accepts `placeId` and `sessionToken`. `POST /chats/{chatId}/planner/places` accepts `{query,sessionToken}` and returns Google Maps `{id,label}` suggestions before a trip exists. On creation, the server resolves the selected provider ID itself. A city becomes a search area with its full provider address; a specific venue remains the exact destination. An optional manually typed city remains supported when Maps is unavailable. The frontend debounces autocomplete and never receives the Google API key.

The new public template also contains `budget: { [memberId]: number|null }`. These are optional volunteered **public demo spending limits in USD**, extracted only from that speaker's current-batch public message or a clearly labeled public edit. They are not bank suggestions, private ceilings or decrypted historical check-ins. The model extracts numbers without performing budget calculations; public travel limit arithmetic remains Python. New conversation planners do not load private preferences for scoring or input fingerprints. Historical encrypted rows and legacy owner-only APIs remain protected and are not removed or migrated into public fields. Unsupported currencies remain unresolved; venue price levels never become dollar estimates.

`POST /trips/{tripId}/planner/respond` takes `{revision: approvalRevision, going, demoSpeakerId?}` and returns `Planner`. This is the binary RSVP shown in the new poll: **Yes, I'm going** records explicit attendance and a confirmation; **Not coming** records an explicit decline. A decline extracted from conversation is already honored. Conditional status is a background waiting state, not a third poll button. Joining the displayed proposal can record `Accepted the proposed timing` when no personal availability or exact agreed time exists; it never guesses exact flight dates. Response ballots accumulate without resetting each other. Later meaningful conversational/manual edits still reset approval. New polls require at least two confirmations while two or more eligible members remain; otherwise the configured percentage threshold still applies. Profile avatars show green checks or red crosses; overflow is collapsed with a named `+N` indicator.

Once enough people confirm, the criteria and going-member set freeze and generation begins automatically. The application presents one recommended choice, using persisted `recommendationRank` (and stable IDs as a fallback) so database row ordering cannot change the chosen widget. A matched supported event is preferred over an unrelated generic venue for an event request. Existing arrays remain available for legacy clients, but the demo does not ask the group to sort or pick a second time.

Only flight and train are offered as transport intent. Confirmed complete flight inputs can reuse the multi-origin engine and owner-scoped widget evidence. Unknown airports/dates, train intent without a verified provider feed, other transport modes, or missing flight results use a real Maps place/stay fallback instead of blocking the demo or fabricating a route/fare. Future room rates, opening hours, tickets and dietary/accessibility suitability remain unknown unless independently sourced. Flight personalization always uses the authenticated viewer; the public demo speaker switcher never impersonates a private widget viewer.

`POST /chats/{chatId}/demo/reset` returns `{resetAt}` and is restricted to the fixed loopback-only local demo identity/chat in development mode. It archives current planners, cancels listening batches, revokes generation leases, and sets a durable conversation cutoff. Group message history and listener context only include messages after that cutoff. Old messages, trip history, private ciphertext and provider records are retained; no production chat or Supabase data is deleted. `chat.reset` carries `{type,chatId,resetAt}`. Clients clear messages/drafts/polls/widgets and ignore stale responses; reconnect/polling recovers the empty active planner. Demo profile illustrations live at `/planner/people/*.svg`; normal users can retain an initials fallback.

Conversation planners open the in-chat RSVP poll as soon as at least half the current chat members have spoken since planner creation (rounded up). Incomplete availability and queued listening do not hide or block the poll. Silent members await a response; conversational declines can be changed with Yes. The approval threshold still controls recommendation generation: participation alone is not approval. Unresolved timing and location remain explicit.
