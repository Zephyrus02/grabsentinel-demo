# test-auth-server

A minimal **FastAPI + PostgreSQL + SQLAlchemy (async) + Alembic** auth server with
server-side rendered UI. Sign up sends a one-time code via [Resend](https://resend.com)
for email verification, then routes the user to a welcome screen with a logout button.

## Stack

- [`uv`](https://docs.astral.sh/uv/) for project / dependency management
- FastAPI + Jinja2 templates (server-side rendered UI)
- SQLAlchemy 2.0 async + `asyncpg`
- Alembic for migrations
- Resend for transactional email
- `bcrypt` for password & OTP hashing
- `SessionMiddleware` (signed cookies) for sessions

## Project layout

```
app/
  config.py            # pydantic-settings
  database.py          # async engine, session, Base
  models.py            # User, OtpCode
  security.py          # bcrypt hashing helpers
  main.py              # FastAPI app + middleware wiring
  routers/auth.py      # signup / verify / login / welcome / logout
  services/
    otp_generator.py   # generate + email a code (separate from verification)
    otp_verifier.py    # verify a code (separate from generation)
    mailer.py          # Resend integration
  templates/           # Jinja2 templates
alembic/               # async-mode Alembic environment
  versions/0001_initial.py
main.py                # re-exports `app` for `fastapi dev` discovery
```

## Setup

1. **Postgres** – make sure a database exists:

   ```bash
   createdb auth_server
   ```

2. **Environment** – copy and edit `.env` (a working `.env` is included for local dev):

   ```bash
   cp .env.example .env
   ```

   Key vars:
   - `DATABASE_URL` – must use the `postgresql+asyncpg://` scheme
   - `SESSION_SECRET_KEY` – any long random string
   - `RESEND_API_KEY` / `RESEND_FROM_EMAIL`

3. **Install deps** – handled automatically by `uv run`, but you can pre-sync:

   ```bash
   uv sync
   ```

## Run migrations

```bash
uv run alembic upgrade head
```

To create new migrations after editing `app/models.py`:

```bash
uv run alembic revision --autogenerate -m "your message"
uv run alembic upgrade head
```

## Run the server

```bash
uv run fastapi dev
```

Then open <http://127.0.0.1:8000/> – you'll be redirected to `/login`.

## Auth flow

1. **`/signup`** – submit email + password → user row is created
   (`is_verified=False`), a 6-digit OTP is generated, hashed, stored in
   `otp_codes`, and emailed via Resend. Browser is redirected to `/verify-otp`.
2. **`/verify-otp`** – submit the code from the email. On success the user is
   marked verified, signed in (session cookie), and redirected to `/welcome`.
   `/resend-otp` re-issues a fresh code.
3. **`/login`** – email + password. Verified users go straight to `/welcome`;
   unverified users get a fresh OTP and are sent through verification.
4. **`/welcome`** – protected page showing the signed-in email with a
   **Log out** button (POST `/logout` clears the session).

OTP generation (`app/services/otp_generator.py`) and verification
(`app/services/otp_verifier.py`) are deliberately kept in **separate modules**
so each concern can be reused / replaced independently.
