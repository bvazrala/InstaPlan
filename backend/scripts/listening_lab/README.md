# Listening Lab

A standalone, local four-person chat simulator for the group-listening feature. It imports nothing from `backend/app/`, uses no Supabase database or auth, and never substitutes mock model results in the dashboard. The browser talks only to a local Python server; that server calls Muse.

## Run

From `backend/`:

```bash
.venv/bin/python -m scripts.listening_lab.server
```

Open <http://127.0.0.1:8765>. The lab reads only `MUSE_API_KEY`, `MUSE_BASE_URL`, and `MUSE_MODEL` from its own `.env` or `backend/.env`; exported shell variables take precedence. It does not load the app's database, Supabase, or other settings. The default model is `muse-spark-1.3`, and the lab rejects any other model. The API key stays in the server process and is never sent to the browser.

Categories are photo cards (Dining, Travel, Entertainment, plus **Custom**, where the user names their own category, for example "Game night"). The photos come from SerpApi Google Images through the lab server (`SERPAPI_KEY`, cached on disk in `.cache/`, so each phrase costs one search). The category label goes to Muse as context, a custom category gets one optional field, `event_type`, and the category photo is display-only (it is never sent to Muse). Tap **+** next to the chat composer and choose **Planner** to start a plan (title, optional location, type). Whoever opens it is only the initiator, not an owner. Then send messages while switching between the four people. Each switch changes the perspective of the chat: that person's messages become “You” on the right, their composer is active, and their personal template fields are highlighted. Messages sent close together are combined into one Muse call. The right panel shows accepted field changes, missing requirements, call counts, token usage, and errors. When the other fields are settled, one final Muse call predicts empty topic fields (cuisine, meal type, trip type, accommodation, activity) only when the notes and context make the answer clear; predicted values are labelled in the template.

For an optional scripted run that **makes real Muse calls**:

```bash
.venv/bin/python -m scripts.listening_lab.replay scripts/listening_lab/fixtures/dining.jsonl
```

Other fixtures cover Travel and Entertainment. Tests use a fake client and make no network calls:

```bash
.venv/bin/python -m pytest scripts/listening_lab/tests
```

The lab holds state in memory; restarting it clears the session. Everything typed in the chat is treated as public: there is no private-data handling here, and `budget` is an ordinary per-person field. `where.destination` is picked from Google Maps (key `GOOGLE_MAPS_API_KEY` in `backend/.env`, used only by the lab server); Muse only suggests a place name as a hint. `where.origins` comes from each member's device location, not from chat. `when.flexibility` treats an explicit “I'm flexible” as `null`; a participant who says nothing about timing remains missing. Muse keeps running notes, sees a few messages before and after each batch, and when the template is complete the chat shows a vote card (40/50/60% threshold) that confirms the plan.

## Paying for the plan (Capital One Nessie)

Once the vote confirms the plan, the person who started it enters the total cost. It is split evenly between them and everyone who voted yes, and each person pays their share with one tap: the lab server makes a real Nessie sandbox transfer from their account to the initiator's (`NESSIE_API_KEY` in `backend/.env`; `NESSIE_BASE_URL` optional). Each simulator user gets a Nessie customer and a $1,500 checking account on first use, remembered in `.cache/nessie.json`. The view shows only the active person's own balance.
