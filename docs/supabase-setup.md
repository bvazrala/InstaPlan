# Supabase setup

About 10 minutes. We use Supabase for two things only: **login (Auth)** and **the Postgres database**. The frontend never reads data from Supabase directly; everything goes through the FastAPI backend.

## 1. Create the project

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard) and click **New project**.
2. Name it `instaplan`. For the database password, click **Generate** and save it in your password manager (you'll need it in step 4).
3. Pick the US region closest to Austin, then **Create new project**. It takes a minute or two.

## 2. Turn on email login

1. **Authentication → Sign In / Providers → Email**: make sure it's enabled.
2. For the hackathon, turn **Confirm email** off so teammates can log in right away (the seed script's demo users are pre-confirmed either way).
3. **Authentication → URL Configuration**: set **Site URL** to `http://localhost:3000`. Add your .tech URL once it's deployed.

## 3. Copy the keys

**Settings → API Keys** (the project URL and publishable key are also in the **Connect** dialog):

| Value | Looks like | Goes in |
| --- | --- | --- |
| Project URL | `https://PROJECT_REF.supabase.co` | `SUPABASE_URL` in `backend/.env`, `NEXT_PUBLIC_SUPABASE_URL` in `frontend/.env.local` |
| Publishable key | `sb_publishable_...` | `SUPABASE_PUBLISHABLE_KEY` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` |
| Secret key | `sb_secret_...` | `SUPABASE_SECRET_KEY` in `backend/.env` **only** |

The secret key bypasses all security. It never goes in the frontend, in GitHub, or in a group chat; share it with backend teammates through a password manager or a direct message. If you only see legacy `anon` / `service_role` keys, create the new ones on the same page (legacy keys still work, but they're being phased out).

## 4. Copy the database connection string

1. Click **Connect** at the top of the project.
2. Choose **Session pooler**. It works on every network (the direct connection needs IPv6, which many networks and hosts lack).
3. Copy the URI and replace `[YOUR-PASSWORD]` with the password from step 1.
4. Change the start from `postgresql://` to `postgresql+psycopg://`, then put it in `backend/.env`:

```
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
```

If your password has characters like `@ # ? &` or spaces, percent-encode them or generate a new password.

## 5. Finish backend/.env

```bash
cd backend
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the output in `PRIVATE_DATA_KEY`. Everyone on the team must use the **same** key, or private answers saved by one backend can't be read by another.

## 6. Create the tables and demo users

```bash
cd backend
source .venv/bin/activate
python -m scripts.seed_demo
```

This creates every table, locks them down, and adds four demo users to Supabase Auth with the password `instaplan-demo-2026`:
`you@demo.instaplan.test`, `maya@demo.instaplan.test`, `alex@demo.instaplan.test`, `sam@demo.instaplan.test`.

**Check it worked:**
- **Authentication → Users** shows the four demo users.
- **Table Editor** shows 12 tables, and none is marked as unrestricted (row-level security is on).

## 7. Try logging in

```bash
cd frontend
npm run dev
```

Open [localhost:3000/login](http://localhost:3000/login) and log in as `you@demo.instaplan.test`. After login the chat still shows demo data until the screens are wired to the backend (see the README's build status).

## Why the tables are locked down

Supabase publishes the `public` schema through its Data API to anyone holding the publishable key, and that key is in every visitor's browser. When the backend starts on Postgres, `app/db.py` turns on row-level security for every table (with no policies) and revokes access from the `anon` and `authenticated` roles. The backend connects as `postgres`, which bypasses row-level security, so it keeps full access. `tests/test_privacy.py` checks this when run against Postgres.

**Never point `TEST_DATABASE_URL` at Supabase:** the tests drop every table.
