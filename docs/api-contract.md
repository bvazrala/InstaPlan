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
| GET | `/trips/{tripId}` | | `Trip` | |
| POST | `/trips/{tripId}/stage` | `{ stage }` | `Trip` | |
| GET | `/trips/{tripId}/facts` | | `Fact[]` | R3, R4 |
| PATCH | `/trips/{tripId}/facts/{factId}` | `{ value }` | `Fact` | R5 |
| DELETE | `/trips/{tripId}/facts/{factId}` | | 204 | R5 |
| POST | `/trips/{tripId}/vote` | `{ going }` | `Trip` | R8 |
| GET | `/trips/{tripId}/options` | | `Option[]` | R12–R14 |
| POST | `/trips/{tripId}/options/generate` | | 202 | R12 |
| POST | `/trips/{tripId}/pick` | `{ optionId }` | `Trip` | R15 |
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

**Server → client events.** Group events go to everyone in the chat. `private.*` events go only to their owner's connections.

| Event | Payload | Sent to |
| --- | --- | --- |
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
                  lodgingShare: number; daily: number; fit: number; certainty: string; cats: Record<Category, number>;
                  fairestRank: number /* never the burden ratio */; people: TravelLeg[]; hue: number;
                  listingUrl?: string; pricedAt?: string };
type PrivatePrefs = { budgetCap: number | null; dietary: string[]; accessibility: string[]; noGos: string;
                      privateScores: Record<string, number> /* -2..+2 */ };
type Stage    = "collecting" | "voting" | "checkin" | "options" | "picked" | "settle";
```

The frontend `Stage` adds `"idle"` for "no trip yet".
