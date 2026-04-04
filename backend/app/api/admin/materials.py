import hashlib
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.material import AudioMaterial
from app.schemas.material import MaterialListItem, MaterialResponse, PaginatedMaterials
from app.services.ffmpeg_service import get_duration, convert_to_cbr_mp3
from app.storage.factory import get_storage

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aac", ".mp4"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_response(material: AudioMaterial) -> MaterialResponse:
    storage = get_storage()
    return MaterialResponse(
        id=material.id,
        title=material.title,
        filename=material.filename,
        file_hash=material.file_hash,
        duration=material.duration,
        status=material.status,
        created_at=material.created_at,
        audio_url=storage.get_url(material.file_path),
    )


@router.get("", response_model=PaginatedMaterials)
async def list_materials(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(select(func.count(AudioMaterial.id)))
    total = total_result.scalar_one()

    result = await db.execute(
        select(AudioMaterial)
        .order_by(AudioMaterial.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    materials = result.scalars().all()

    storage = get_storage()
    items = [
        MaterialListItem(
            id=m.id,
            title=m.title,
            filename=m.filename,
            duration=m.duration,
            status=m.status,
            created_at=m.created_at,
            audio_url=storage.get_url(m.file_path),
        )
        for m in materials
    ]

    return PaginatedMaterials(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post("", response_model=MaterialResponse, status_code=201)
async def upload_material(
    file: UploadFile = File(...),
    title: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {suffix}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    data = await file.read()
    file_hash = _sha256(data)

    # dedup check
    existing = await db.execute(
        select(AudioMaterial).where(AudioMaterial.file_hash == file_hash)
    )
    duplicate = existing.scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This audio file has already been uploaded.",
                "existing_id": duplicate.id,
                "existing_title": duplicate.title,
            },
        )

    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    storage = get_storage()

    # 1. 原始文件存为临时路径（带原始后缀）
    tmp_filename = f"{ts}_tmp{suffix}"
    tmp_path = await storage.save(data, tmp_filename)

    # 2. 转换为 CBR MP3（最终入库的文件）
    final_filename = f"{ts}.mp3"
    final_path = str(Path(tmp_path).parent / final_filename)
    try:
        await convert_to_cbr_mp3(tmp_path, final_path)
    except Exception as e:
        # 转换失败时清理临时文件，不入库
        Path(tmp_path).unlink(missing_ok=True)
        logger.error(f"CBR conversion failed for {tmp_path}: {e}")
        raise HTTPException(status_code=500, detail="Audio conversion failed")
    finally:
        # 无论成功失败都删临时文件
        Path(tmp_path).unlink(missing_ok=True)

    duration = await get_duration(final_path)

    material = AudioMaterial(
        title=title,
        filename=file.filename,       # 保留原始文件名供展示
        file_path=final_path,         # 存 CBR MP3 路径
        file_hash=file_hash,          # hash 仍基于原始内容，保证去重逻辑不变
        duration=duration,
        status="pending",
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    logger.info(f"Uploaded material id={material.id} title={material.title!r} (CBR MP3)")
    return _build_response(material)


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(AudioMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return _build_response(material)


@router.delete("/{material_id}", status_code=204)
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(AudioMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    storage = get_storage()
    await storage.delete(material.file_path)

    await db.delete(material)
    await db.commit()
    logger.info(f"Deleted material id={material_id}")