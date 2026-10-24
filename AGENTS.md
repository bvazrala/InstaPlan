# Instructions for AI coding assistants

InstaPlan is a group-chat trip planner. Read `README.md` first; `docs/api-contract.md` is the frontend ↔ backend contract.

## Privacy rules (never break these)

Friends must never see each other's private information, and the group-chat AI must never hold it.

- Never send budgets, bank data, private check-in answers or a `PrivateContext` to `backend/app/integrations/muse.py`. Muse functions take a `GroupContext` only.
- Private data lives in `PrivatePrefs` and `PrivateMessage`, encrypted with `app/privacy/crypto.py`. Only `/trips/{id}/me/` routes, `integrations/gemini.py` and `app/logic/` may read it.
- Never add a route that takes a user id and returns private data. Private routes act on the logged-in user.
- Every route calls `require_trip_member` or `require_chat_member` (`app/privacy/access.py`).
- Never add burden ratios, ceilings or budgets to `schemas.OptionOut` or any group response.
- Send private events through `hub.to_user` with a `private.*` type; never `hub.to_chat`.
- Never log private values. Never put API keys in `frontend/` or in any `NEXT_PUBLIC_` variable.
- Budget math stays in plain Python (`app/logic/`), not in a model prompt.

## Where things go

- Pure math with no I/O → `backend/app/logic/` with a test in `tests/test_logic.py`.
- A third-party API → `backend/app/integrations/`, cached through `integrations/cache.py`.
- Prompt wording → `backend/app/prompts/*.md`.
- UI that shows one person's private data → `frontend/components/private/`.
- Shared frontend types → `frontend/lib/types.ts`, matching `backend/app/schemas.py` (camelCase JSON).

## Before you finish

- `cd backend && pytest` (the privacy suite must pass)
- `cd frontend && npm run lint && npm run build`
- Next.js 16 has breaking changes: read `frontend/node_modules/next/dist/docs/` before using an unfamiliar API.
