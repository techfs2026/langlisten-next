from sqlalchemy import Integer, Float, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Subtitle(Base):
    __tablename__ = "subtitles"
    __table_args__ = (
        UniqueConstraint("material_id", "seq", name="uq_subtitle_material_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("audio_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)   # seconds, ms precision
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    material: Mapped["AudioMaterial"] = relationship(  # noqa: F821
        "AudioMaterial",
        back_populates="subtitles",
    )