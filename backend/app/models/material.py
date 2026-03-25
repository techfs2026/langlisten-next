from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AudioMaterial(Base):
    __tablename__ = "audio_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)   # original filename
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)  # storage path / key
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)  # SHA256
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )
    # pending → transcribing → transcribed → verified

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    subtitles: Mapped[list["Subtitle"]] = relationship(  # noqa: F821
        "Subtitle",
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="Subtitle.seq",
    )