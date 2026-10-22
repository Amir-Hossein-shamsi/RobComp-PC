from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# TWO base classes: Base owns/creates RTDS; ReflectedBase only mirrors Django-managed tables and must never create/alter them

class Base(DeclarativeBase):
    pass

class ReflectedBase(DeclarativeBase):
    pass

class RTDS(Base):
    __tablename__ = "RTDS"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    bid: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    ask: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    day_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_rtds_symbol_source_ts", "symbol", "source_ts"),
        Index("ix_rtds_ingested_at", "ingested_at"),
    )

class DjangoUser(ReflectedBase):
    __tablename__ = "django_app_user"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(150))
    first_name: Mapped[str] = mapped_column(String(150))
    last_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254))
    is_active: Mapped[bool] = mapped_column(default=True)

class DjangoUserProfile(ReflectedBase):
    __tablename__ = "django_app_userprofile"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)