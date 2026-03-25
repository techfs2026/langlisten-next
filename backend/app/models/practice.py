from datetime import datetime, timezone
from sqlalchemy import Integer, Float, Boolean, Text, ForeignKey, DateTime, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        index=True,
        unique=True,
        nullable=False,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("audio_materials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    attempts: Mapped[list["SentenceAttempt"]] = relationship(
        "SentenceAttempt",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class SentenceAttempt(Base):
    __tablename__ = "sentence_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subtitle_id: Mapped[int] = mapped_column(
        ForeignKey("subtitles.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)   # 0.0 ~ 1.0
    time_spent: Mapped[int | None] = mapped_column(Integer, nullable=True)  # milliseconds
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    session: Mapped["PracticeSession"] = relationship(
        "PracticeSession",
        back_populates="attempts",
    )