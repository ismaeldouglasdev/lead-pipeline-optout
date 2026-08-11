# Lead Pipeline Opt-Out Service

Public unsubscribe endpoint for the (private) lead outreach pipeline.

A lead clicks the unsubscribe link in an outreach email:
`https://opt-out.ismaeltech.com/opt-out?email=lead@example.com`

## What this repo contains

- `app/main.py` — FastAPI app
- `app/routes/optout.py` — GET `/opt-out` (confirmation page) + POST `/opt-out`
  (RFC 8058 one-click List-Unsubscribe) + GET `/api/optouts` (sync endpoint)
- `app/models.py` — `optouts` table (email + timestamp only)
- `render.yaml` — Render blueprint (free tier)

## How it works

1. The **private** pipeline embeds the unsubscribe link in every outreach email,
   plus RFC 8058 headers (`List-Unsubscribe`, `List-Unsubscribe-Post`).
2. When a lead clicks (or a mail client auto-POSTs), this public service
   records `email + timestamp` in its own Postgres table.
3. The private pipeline periodically calls `GET /api/optouts?since=<ISO>`,
   picks up new opt-outs, and marks the matching local leads as
   `opt_out=True` so they are never emailed again.

**No lead database is ever exposed here.** Only the emails of people who
explicitly opted out (i.e. the addresses they themselves submitted).

## Deploy (Render, free)

1. Create a free Postgres (Neon, or Render's own free Postgres) and copy the
   connection string.
2. In Render: New → Blueprint → select this repo. Set the `DATABASE_URL`
   env var to the Postgres connection string (format
   `postgresql://user:pass@host:port/db`).
3. Deploy. The service listens on `$PORT` (Render sets it automatically).

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8090
curl "http://localhost:8090/opt-out?email=test@example.com"
```

## License

Private — not for external use.
