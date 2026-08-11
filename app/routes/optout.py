"""Opt-out service — public unsubscribe endpoint (LGPD/RFC 8058 compliant).

A lead clicks the unsubscribe link in an outreach email:
    GET https://opt-out.ismaeltech.com/opt-out?email=lead@example.com

This service records the opt-out in its OWN table (persistent Postgres on the
cloud). The private lead-pipeline polls this service periodically and marks
the matching local leads as opted out — without exposing the lead database.

Design goals:
- Zero knowledge about the lead DB (no email enumeration: unknown emails get
  the same generic confirmation page).
- Idempotent: clicking twice is a no-op.
- RFC 8058 List-Unsubscribe-Post: the same endpoint accepts POST with
  `List-Unsubscribe=One-Click`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import OptOut

logger = logging.getLogger(__name__)

router = APIRouter(tags=["opt-out"])


def _confirmation_html(language: str | None) -> str:
    """Confirmation page (pt-BR default, en for English leads)."""
    if language and language.lower().startswith("en"):
        title = "You're unsubscribed"
        body = (
            "You've been removed from our outreach list. "
            "You won't receive any more emails from us."
        )
        back = "If this was a mistake, no action needed — you can simply ignore this page."
    else:
        title = "Você foi removido"
        body = (
            "Seu e-mail foi removido da nossa lista de contato. "
            "Você não receberá mais emails nossos."
        )
        back = "Se foi um engano, não precisa fazer nada — é só ignorar esta página."

    lang = "en" if language and language.lower().startswith("en") else "pt-BR"
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           background: #f4f5f7; display: flex; align-items: center; justify-content: center;
           min-height: 100vh; margin: 0; }}
    .card {{ background: #fff; border-radius: 12px; padding: 48px 40px; max-width: 420px;
            box-shadow: 0 4px 24px rgba(0,0,0,.08); text-align: center; }}
    .check {{ font-size: 48px; margin-bottom: 12px; }}
    h1 {{ font-size: 22px; margin: 0 0 12px; color: #1a1a2e; }}
    p {{ color: #555; line-height: 1.6; margin: 0 0 8px; font-size: 15px; }}
    .small {{ font-size: 13px; color: #999; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="check">✅</div>
    <h1>{title}</h1>
    <p>{body}</p>
    <p class="small">{back}</p>
  </div>
</body>
</html>"""


async def _record_optout(session: AsyncSession, email: str) -> None:
    """Insert or update the opt-out row (idempotent)."""
    normalized = email.strip().lower()
    now = datetime.now(timezone.utc)

    existing = (
        await session.execute(select(OptOut).where(OptOut.email == normalized))
    ).scalar_one_or_none()

    if existing is None:
        session.add(OptOut(email=normalized, opt_out_at=now))
        logger.info("opt-out: new opt-out for %s", normalized)
    else:
        logger.info("opt-out: already opted out (%s)", normalized)
        existing.opt_out_at = now
    await session.commit()


@router.get("/opt-out")
@router.post("/opt-out")
async def opt_out(
    request: Request,
    email: str = "",
    session: AsyncSession = Depends(get_session),
):
    """Record an opt-out.

    GET  -> confirmation HTML page (link in email footer)
    POST -> RFC 8058 one-click: body is `List-Unsubscribe=One-Click`,
            reply is 200 plain text.
    """
    # RFC 8058: mail clients POST to the SAME URL (query string intact),
    # with body `List-Unsubscribe=One-Click`. The email comes from the query
    # string; the List-Unsubscribe header only holds the link URLs.
    if request.method == "POST" and not email:
        body = (await request.body()).decode("utf-8", "replace")
        if "List-Unsubscribe=One-Click" in body:
            # Try to recover the address from the URL query in the header
            # (only used when the client stripped the query string).
            header = request.headers.get("List-Unsubscribe", "")
            import re

            match = re.search(r"[?&]email=([^&\s<>]+)", header)
            if match:
                from urllib.parse import unquote

                email = unquote(match.group(1))

    normalized = (email or "").strip().lower()

    if not normalized:
        # Generic confirmation — never reveal state.
        return _confirmation_html("pt")

    await _record_optout(session, normalized)

    if request.method == "POST":
        return PlainTextResponse("unsubscribed", status_code=200)

    # Language is unknown here (no lead DB access) — pt-BR default is fine.
    return _confirmation_html("pt")


@router.get("/api/optouts")
async def list_optouts(
    since: str = "",
    session: AsyncSession = Depends(get_session),
):
    """Sync endpoint for the private pipeline.

    Returns opt-outs created/updated after `since` (ISO timestamp).
    Only emails are exposed — never the full lead database.
    """
    stmt = select(OptOut).order_by(OptOut.opt_out_at)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            since_dt = None
        if since_dt is not None:
            stmt = stmt.where(OptOut.opt_out_at > since_dt)

    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "optouts": [
            {"email": r.email, "opt_out_at": r.opt_out_at.isoformat()} for r in rows
        ],
    }


@router.get("/health")
async def health():
    return {"status": "ok"}
