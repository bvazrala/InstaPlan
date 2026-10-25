# InstaPlan

**A group planner that lives inside the chat.** Start a Dining, Travel, or Entertainment plan from **+ Planner**, optionally pick a city or exact place from Google Maps, and let the conversation build the template. Friends respond with “Yes, I’m going” or “Not coming”; enough confirmations trigger one sourced recommendation widget. The hackathon demo has no private check-in step. Only voluntarily public spending limits enter its template; historical encrypted private records stay protected.

Built at HackTX 2026 for the Meta, SerpApi and Capital One tracks, with a .tech domain from MLH.

---

## Contents

1. [The problem](#the-problem)
2. [How it works](#how-it-works)
3. [Tech stack](#tech-stack)
4. [Repo layout](#repo-layout)
5. [Getting started](#getting-started)
6. [Privacy and security](#privacy-and-security)
7. [Build status](#build-status)
8. [Who owns what](#who-owns-what)
9. [Team conventions](#team-conventions)
10. [Deploying](#deploying)

---

## The problem

Group trips die in the chat. Plans scatter across hundreds of messages, nobody owns the planning, and people stay quiet about budget or dietary limits so they don't seem difficult. Many go along with plans they can't afford.

InstaPlan does two things existing planners don't:

- **It collects preferences passively** from the conversation. Nobody fills out a survey.
- **It plans around private constraints the group never sees.** The "Fairest" sort ranks options by the heaviest burden on any one friend's private budget.

## How it works

1. **Start.** Choose **+ → Planner**, enter a title, optionally choose a Google Maps city/exact venue, then pick Dining, Travel or Entertainment.
2. **Converse.** The listener fills public attendance, agreed timing, availability, destination/search area, optional origins, volunteered spending limits, preferences, hard constraints and the active topic's optional fields.
3. **Respond.** A compact plan-and-poll card appears automatically when the required template is ready. Profile pictures show confirmations and declines; conditional attendance stays in the background. Responses are **Yes, I’m going** and **Not coming**. Explicit conversational declines are honored.
4. **Get one recommendation.** Enough confirmations freeze the plan and trigger bounded provider searches. One recommended choice appears with the supplied formation animation. Sourced flight, concert and college-football cards can have a second place/stay fallback slide. Train or unsupported/incomplete travel data uses the real place/stay fallback; no rail fare is fabricated.
5. **Reset the demo.** **Reset demo** clears the visible conversation and active planner, cancels obsolete work and lets the crew start again. Historical records and encrypted data are retained. The four-person public speaker switcher does not change the authenticated viewer of personalized flight data.

## Tech stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, lucide-react |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLModel, httpx |
| Real-time | FastAPI WebSockets: one channel per chat, plus private events per user |
| Database and login | Supabase (PostgreSQL + Auth). SQLite locally until Supabase is set up |
| AI | Meta Muse Spark 1.3 (Standard) via the OpenAI Python SDK: group assistant and private check-ins, as separate requests |
| Travel data | SerpApi: Google Flights, Google Hotels (vacation rentals), Google Maps |
| Money | Capital One Nessie sandbox: accounts, bills, transfers |
| Hosting | Vercel (frontend + .tech domain), Railway or Render (backend), Supabase |

Not using: Redis, Celery, Docker orchestration, microservices, a mobile app, LangChain.

## Repo layout

```
instaplan/
├── README.md
├── AGENTS.md                  Rules for AI coding assistants working in this repo
├── docs/
│   ├── api-contract.md        REST routes and WebSocket events: the frontend ↔ backend agreement
│   └── supabase-setup.md      Step-by-step Supabase setup
│
├── frontend/                  Next.js app
│   ├── app/                   Routes
│   │   ├── page.tsx           /               Chat app
│   │   ├── login/             /login          Supabase email login
│   │   └── trip/[tripId]/     /trip/:id       Full trip page: heat map + comparison
│   ├── components/
│   │   ├── chat/              Chat shell: list, thread, bubbles, top bar, side panel, mobile sheet
│   │   ├── trip/              Trip flow: trip card, stage panel, collect, vote, summary, settle
│   │   │   └── options/       Option cards, sort bar, fit pill, heat map
│   │   ├── private/           Anything that shows one person's private data (check-in, privacy banner)
│   │   └── ui/                Shared buttons, cards, chips, labels
│   ├── lib/
│   │   ├── types.ts           Shared types, mirrors the backend's JSON
│   │   ├── api.ts             REST client (adds the login token)
│   │   ├── socket.ts          WebSocket client
│   │   ├── supabase.ts        Login only; data goes through the backend
│   │   ├── sort.ts            Client-side re-sort of priced options
│   │   ├── format.ts          Money and fit colors
│   │   └── trip-context.tsx   Trip UI state
│   └── mocks/demo-data.ts     Demo data the UI runs on until each API is wired
│
└── backend/                   FastAPI app
    ├── app/
    │   ├── main.py            App, CORS, routers           → uvicorn app.main:app
    │   ├── config.py          Every env var and secret
    │   ├── db.py              Engine and sessions
    │   ├── auth.py            Verifies Supabase tokens
    │   ├── models.py          Database tables
    │   ├── schemas.py         API shapes: only fields declared here reach the browser
    │   ├── realtime.py        WebSocket hub: chat channel vs. private events
    │   ├── pipeline.py        After each message: trip offer, fact extraction; option generation
    │   ├── privacy/           Access checks, encryption, GroupContext vs. PrivateContext
    │   ├── routers/           chats, trips, checkins (owner only), options, expenses, ws
    │   ├── logic/             Pure math: fit score, ranking, budget ceiling, settle up, trip stages
    │   ├── integrations/      Muse (group side, private side), SerpApi, Nessie, response cache
    │   └── prompts/           Prompt text for the AI models (edit without touching code)
    ├── scripts/seed_demo.py   Demo users, group chat, scripted messages, Nessie accounts
    └── tests/                 Privacy suite (test_privacy.py) and logic tests
```

## Getting started

**You need:** Node 22.13+ and Python 3.11+. Use local demo mode below to work without Supabase, or configure authenticated chat with [docs/supabase-setup.md](docs/supabase-setup.md).

### Local demo without login

In `backend/.env`, set `APP_ENV=dev` and `DEMO_MODE=true`, then start the backend
from `backend/` and the frontend from `frontend/` using the commands below. Open
[localhost:3000](http://localhost:3000); no username, password or Supabase project is
needed. The browser discovers this mode from the backend, including WebSocket access.

Demo mode uses the fixed Jordan identity, four synthetic group members, and a
ready-to-price New York trip with different departure airports. Data persists in
`backend/instaplan-demo.db`, isolated from `DATABASE_URL` and your existing database.
No Supabase users are created or contacted. Membership checks and owner-only private
routes remain enforced. The mode is rejected outside `APP_ENV=dev`, accepts only
loopback clients/trusted browser origins, and must be served on 127.0.0.1.

Muse and SerpApi remain real optional integrations using backend keys. Starting the
demo makes no paid requests; click **Generate options** to request live prices.
To restore normal Supabase authentication, set `DEMO_MODE=false` and restart the
backend, then reload the browser. Your original database URL and Supabase settings
are preserved. An unavailable backend does not silently enable demo sessions.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # fill in keys as you get them
python -m scripts.seed_demo        # demo users, chat and messages (add --nessie for bank accounts)
uvicorn app.main:app --reload      # API docs: http://localhost:8000/docs
pytest                             # run before every merge (TEST_DATABASE_URL=<scratch Postgres> to test on Postgres)
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                        # http://localhost:3000
npm test && npm run lint && npm run build # run before every merge
```

### Keys checklist

| Key | Where to get it | Goes in |
| --- | --- | --- |
| Supabase URL + publishable key (`sb_publishable_`) | Supabase → Settings → API Keys | `backend/.env` and `frontend/.env.local` |
| Supabase secret key (`sb_secret_`) | Same page | `backend/.env` only (seed script) |
| `DATABASE_URL` | Supabase → **Connect** → Session pooler (see [Supabase setup](docs/supabase-setup.md)) | `backend/.env` |
| `PRIVATE_DATA_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | `backend/.env` |
| Muse Spark | Meta booth or dev.meta.ai; use `muse-spark-1.3`, never a `-contributor` model | `backend/.env` |
| SerpApi | serpapi.com dashboard | `backend/.env` |
| Nessie | nessieisreal.com profile page | `backend/.env` |

Only `NEXT_PUBLIC_` values go in the frontend, because Next.js ships them to the browser.

## Privacy and security

**The promise: no friend ever sees another friend's private information, and no request about the group chat ever carries it.** Each rule is enforced in code and covered by `backend/tests/test_privacy.py`.

| Rule | Where it's enforced |
| --- | --- |
| The server decides who sees what. Private routes live under `/trips/{id}/me/` and never take a user id from the client | `routers/checkins.py`, `privacy/access.py` |
| Non-members get 404, so they can't probe what exists | `privacy/access.py` |
| Private answers and check-in messages are stored in their own tables, encrypted | `models.py`, `privacy/crypto.py` |
| Group and private AI work are separate, stateless Muse requests in separate modules: group prompts accept only a `GroupContext`, check-ins only one member's `PrivateContext` | `privacy/context.py`, `integrations/muse_group.py`, `integrations/muse_private.py` |
| Muse runs on a Standard model, which Meta doesn't train on; `-contributor` models are refused | `integrations/muse_client.py` |
| Supabase's Data API can't read our tables: every table gets row-level security and the browser roles lose access | `db.py` |
| `PrivateContext` prints as `<redacted>`, so it can't leak into logs | `privacy/context.py` |
| `private.*` events go only to their owner; the hub refuses to broadcast them | `realtime.py` |
| Options carry a fairest rank, never the burden ratio (similar costs would reveal the tightest budget) | `logic/ranking.py`, `schemas.OptionOut` |
| Budget ceilings are plain math, not a model, and Muse gets numbers, not transactions | `logic/budget.py`, `integrations/muse_private.py` |
| Private budgets only shape options in groups of 3 or more | `privacy/access.py` |
| The WebSocket token goes in the first message, not the URL, so it stays out of logs | `routers/ws.py`, `frontend/lib/socket.ts` |
| All API keys stay on the server | `config.py`, `frontend/.env.example` |

`test_privacy.py` includes a sweep that requests every GET route as one member after another member saved private answers, and fails if any response contains them. Show it to judges.

**Adding an endpoint? Check four things:**
1. It calls `require_trip_member` or `require_chat_member`.
2. Its response model in `schemas.py` has no private field.
3. Private data only flows to `/me/` routes, `muse_private.py`, or `logic/`.
4. `pytest` still passes.

## Build status

Requirement ids (R1–R23) match the [MVP requirements doc](https://claude.ai/artifact/CrHqorKajgLeBzuyFhqVjT). Every screen in the UI already exists on demo data. "Wire" means connecting it to the backend.

"Done" means implemented and tested locally. The Muse, SerpApi and Nessie calls haven't been run against live keys yet, so test each one as soon as you have its key.

| Feature | Req | Backend | Frontend |
| --- | --- | --- | --- |
| Login | R20 | Done (`auth.py`) | Done (`/login`); add session guard |
| Real-time group chat | R21 | Done (REST + WebSocket) | Done: backend chat list, members, history, sends, and live updates |
| Start trip, trip-intent offer | R1, R2 | Done (keyword check + `trip.offer` event) | Wire |
| Facts from chat, live trip card | R3, R4 | Pipeline wired to Muse; tune `prompts/extract_facts.md` | Wire |
| Edit or delete a fact | R5 | Done | Wire the pencil button |
| One-tap nudges | R6 | `muse.write_nudge` ready; trigger it | Wire |
| Vote to lock in | R8 | Done | Wire |
| Private check-in thread | R9, R22 | Done (Muse, private side); start it on lock-in | Show as a private thread, wire |
| Final-touches summary | R10 | To do | To do |
| Nessie budget suggestion | R11 | Done | Wire |
| Generate options (SerpApi) | R12 | Implemented: bounded multi-origin pricing, fit, ranking and background generation; live-key smoke pending | Live cards, comparison and picking |
| Sort and fit colors | R13, R14 | Four strategies, hard-constraint evaluation and privacy-safe fit | Live local sorts, exact allocations and unverified-state labels |
| Pick an option | R15 | Done | Wire |
| Tweak in plain words | R16 | To do | Input exists |
| Settle up through Nessie | R17 | Done | Wire |
| Privacy test suite | R23 | Done (18 tests) | |
| Trip poster (Muse Image) | R18 | Stretch | Placeholder exists |
| Voice notes, local outings | R7, R19 | Stretch | |

**Wiring a screen:** replace its import from `@/mocks/demo-data` with `apiFetch` (from `lib/api.ts`) or a WebSocket event (from `lib/socket.ts`). Shapes are in `lib/types.ts` and [`docs/api-contract.md`](docs/api-contract.md).

## Who owns what

| Workstream | Folders |
| --- | --- |
| **Chat app** | `frontend/app`, `frontend/components/{chat,private,ui}`, `frontend/lib/{api,socket,supabase}.ts` |
| **AI** | `backend/app/integrations/muse_{client,group,private}.py`, `backend/app/prompts/`, `backend/app/pipeline.py` (`on_group_message`), `backend/app/privacy/context.py` |
| **Data and ranking** | `backend/app/integrations/{serpapi_client,cache}.py`, `backend/app/logic/{fit,ranking}.py`, `pipeline.generate_options`, `frontend/components/trip/options/` |
| **Backend and money** | `backend/app/{main,db,auth,models,schemas,realtime}.py`, `backend/app/routers/`, `backend/app/integrations/nessie.py`, `backend/app/logic/{budget,settle}.py`, `backend/scripts/`, `backend/tests/` |

Changing `models.py`, `schemas.py`, `lib/types.ts` or `docs/api-contract.md`? Tell the team first: everyone depends on them.

## Team conventions

- **Branches:** `name/short-feature`, e.g. `maya/vote-wiring`. Small PRs, merged often. Nobody pushes to `main` directly.
- **Before merging:** `pytest` in `backend/`, then `npm run lint && npm run build` in `frontend/`.
- **Never commit** `.env`, `.env.local` or any key. Only the `.env.example` files are tracked.
- **API changes:** update `docs/api-contract.md` and `frontend/lib/types.ts` in the same PR.
- **Next.js 16 differs from older versions.** Check `frontend/node_modules/next/dist/docs/` before using an unfamiliar API (see `frontend/AGENTS.md`).

## Deploying

| Part | Where | Settings |
| --- | --- | --- |
| Frontend | Vercel | Root directory `frontend`; set the `NEXT_PUBLIC_` vars; attach the .tech domain |
| Backend | Railway or Render | Root directory `backend`; start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; set every var from `.env.example`, with `FRONTEND_ORIGIN` set to the .tech URL |
| Database + Auth | Supabase | Already hosted |

Deploy the backend on day one, not the last hour: WebSockets need a persistent server, which is why it isn't on Vercel.

---

The frontend UI started as the original InstaPlan prototype and was reorganized into this structure.

## Unified planner development flow

In the local demo, open a group chat and choose **+ → Planner**. Name the plan and choose Dining, Travel, or Entertainment. The four-person switcher changes public message attribution and the public fields being edited; your private account never changes. There is no automatically approved seeded trip.

Conversation updates a persisted public template. Members can correct attendance and availability, approve the initial criteria, see real recommendations and pick a saved result. Travel asks for exact flight dates and confirmed airports after initial approval. **Revise plan** requires fresh approval. Venue costs, ticket availability and future opening hours are explicit unknowns; flight/lodging options retain exact participant allocations and private fairness evaluation.

The normal application contains useful listening and recovery states. Raw model traces and diagnostics remain in `backend/scripts/listening_lab`, which is not imported by production code. Planner sessions, revision-scoped approvals, durable listening batches and venue results are created through the existing startup table/RLS mechanism. Existing trip history is preserved.

Optional Places picking uses server-only `GOOGLE_MAPS_API_KEY`; missing provider keys show unavailable states. Tests mock providers and do not need keys or make paid requests. See `docs/api-contract.md` for the unified API and privacy boundary.


The planner now opens with a readable public summary; **Edit details** reveals corrections when needed. Approval leaves a persistent **Plan confirmed** card in the chat, followed by a widget adapted from the supplied design handoff. Venue and stay photos/reviews come from provider results, not gallery samples. Concert/college-football slides use matching SerpApi event listings; an optional owner-only flight action requires a confirmed origin, explicit permission and a safe provider booking URL. Missing evidence keeps the common place/stay card. The train presentation is available but no live train provider is configured.

Conversation planners open the in-chat RSVP poll as soon as at least half the current chat members have spoken since planner creation (rounded up). Incomplete availability and queued listening do not hide or block the poll. Silent members await a response; conversational declines can be changed with Yes. The approval threshold still controls recommendation generation: participation alone is not approval. Unresolved timing and location remain explicit.
