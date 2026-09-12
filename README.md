# RemindMeApp

An internal web app for employees to track their own reminders (about
emails or anything else) and get a Microsoft 365 email digest of open
tasks every workday morning, sent via Microsoft Graph.

## Features

- Sign in with your Microsoft work account (Azure AD / Entra ID).
- Add a reminder with a title, optional notes, and an optional
  "remind me after" date. Reminders with a future date are snoozed and
  hidden from your open list and digest emails until that date passes.
- Check a box to mark a reminder done. Done items disappear from your
  open list and digest emails but stay in the app and are searchable.
- Every Monday-Friday morning, each user gets an email (sent via Microsoft
  Graph, as themselves) listing their current open reminders.
- A "email me this list now" button to trigger your digest on demand.
- Search across all your reminders, including completed ones.

## How it works

- **Flask** web app, **SQLite** (via SQLAlchemy) for storage.
- **MSAL** (`msal` package) handles Microsoft sign-in using the OAuth2
  authorization code flow with delegated Graph permissions (`User.Read`,
  `Mail.Send`, `offline_access`). Emails are sent from `/me/sendMail`, i.e.
  from the signed-in user's own mailbox to themselves.
- Each user's MSAL token cache (including refresh token) is persisted in
  the database so the background scheduler can silently refresh an access
  token and send the morning digest even if the user isn't actively logged
  in at the time.
- **APScheduler** runs an in-process cron job (`app/scheduler.py`) that
  fires weekday mornings and calls `send_daily_digests`, which emails every
  user their open (non-snoozed, non-done) tasks.

## Setup

### 1. Register an app in Azure AD / Entra ID

1. Go to https://portal.azure.com -> **Azure Active Directory** ->
   **App registrations** -> **New registration**.
2. Set a name (e.g. "RemindMeApp"), leave supported account types as your
   organization only, and set the redirect URI to
   `http://localhost:5000/auth/callback` (type: **Web**). Add your
   production URL's `/auth/callback` too once you deploy.
3. Under **Certificates & secrets**, create a new client secret and copy
   its value.
4. Under **API permissions**, add **Microsoft Graph** delegated
   permissions: `User.Read`, `Mail.Send`, `offline_access`. If your tenant
   requires admin consent, have an admin grant consent for these.
5. Copy the **Application (client) ID** and **Directory (tenant) ID** from
   the app's Overview page.

### 2. Configure the app

```bash
cp .env.example .env
```

Fill in `.env` with your `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, a
random `SECRET_KEY`, and the `APP_BASE_URL` you'll run the app on. Adjust
`DIGEST_HOUR` / `DIGEST_MINUTE` / `TIMEZONE` for when the morning email
should go out.

### 3. Install and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Visit http://localhost:5000, sign in with Microsoft, and start adding
reminders.

For production, run behind a WSGI server, e.g.:

```bash
gunicorn -w 1 -b 0.0.0.0:8000 run:app
```

Use only **one** worker process (`-w 1`) since the digest scheduler runs
in-process; running multiple workers would send duplicate emails. If you
need multiple web workers, set `ENABLE_SCHEDULER=0` and instead run the
digest job from a separate single process (e.g. a small script calling
`app.digest.send_daily_digests`) on its own schedule (cron, a scheduled
task, etc.).

## Notes

- The app only ever reads/sends mail on behalf of the signed-in user via
  delegated Graph permissions — it never gets standing access to anyone's
  mailbox beyond what they've personally signed in and consented to.
- Data model: each reminder (`Task`) has a title, optional notes, an
  optional `remind_after` date, and a `done` flag with a `done_at`
  timestamp. Marking a reminder done never deletes it, so it remains
  searchable from the Search page.
