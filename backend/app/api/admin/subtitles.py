import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.material import AudioMaterial
from app.models.subtitle import Subtitle
from app.schemas.subtitle import SubtitleBatchUpdate, SubtitleListResponse, SubtitleResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{material_id}/subtitles", response_model=SubtitleListResponse)
async def get_subtitles(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(AudioMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    result = await db.execute(
        select(Subtitle)
        .where(Subtitle.material_id == material_id)
        .order_by(Subtitle.seq)
    )
    subtitles = result.scalars().all()
    verified_count = sum(1 for s in subtitles if s.is_verified)

    return SubtitleListResponse(
        material_id=material_id,
        subtitles=[SubtitleResponse.model_validate(s) for s in subtitles],
        total=len(subtitles),
        verified_count=verified_count,
    )


@router.put("/{material_id}/subtitles", response_model=SubtitleListResponse)
async def update_subtitles(
    material_id: int,
    payload: SubtitleBatchUpdate,
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(AudioMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # validate all subtitle ids belong to this material
    subtitle_ids = [s.id for s in payload.subtitles]
    result = await db.execute(
        select(Subtitle).where(
            Subtitle.id.in_(subtitle_ids),
            Subtitle.material_id == material_id,
        )
    )
    db_subtitles = {s.id: s for s in result.scalars().all()}

    if len(db_subtitles) != len(subtitle_ids):
        raise HTTPException(
            status_code=400,
            detail="Some subtitle IDs not found or don't belong to this material",
        )

    for item in payload.subtitles:
        sub = db_subtitles[item.id]
        sub.start_time = item.start_time
        sub.end_time = item.end_time
        sub.text = item.text
        sub.is_verified = item.is_verified

    # update material status based on verification progress
    all_subtitles = list(db_subtitles.values())
    verified_count = sum(1 for s in all_subtitles if s.is_verified)
    material.status = "verified" if verified_count == len(all_subtitles) else "transcribed"

    await db.commit()

    logger.info(
        f"Updated {len(payload.subtitles)} subtitles for material {material_id}, "
        f"status={material.status}"
    )

    # re-fetch to return fresh data
    result = await db.execute(
        select(Subtitle)
        .where(Subtitle.material_id == material_id)
        .order_by(Subtitle.seq)
    )
    subtitles = result.scalars().all()

    return SubtitleListResponse(
        material_id=material_id,
        subtitles=[SubtitleResponse.model_validate(s) for s in subtitles],
        total=len(subtitles),
        verified_count=sum(1 for s in subtitles if s.is_verified),
    )