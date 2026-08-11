"""Opt-out record model — a separate table from the lead pipeline.

Only stores email + timestamp. No lead PII beyond the address that opted out
(which the lead themselves submitted).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class OptOut(Base):
    __tablename__ = "optouts"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    opt_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
