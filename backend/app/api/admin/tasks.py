"""
Admin task endpoints:
  POST /api/admin/materials/{id}/transcribe   trigger Celery task
  GET  /api/admin/tasks/{task_id}/progress    SSE progress stream
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_progress
from app.models.material import AudioMaterial
from app.tasks.transcribe import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/materials/{material_id}/transcribe")
async def trigger_transcribe(
    material_id: int,
    language: str = "en",
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(AudioMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if material.status == "transcribing":
        raise HTTPException(status_code=409, detail="Transcription already in progress")

    task = transcribe_audio.delay(material_id, language)
    logger.info(f"Queued transcription task {task.id} for material {material_id}")

    return {"task_id": task.id, "material_id": material_id}


@router.get("/tasks/{task_id}/progress")
async def task_progress(task_id: str):
    """
    SSE endpoint. Streams progress until status is 'done' or 'error'.

    Event format:
        data: {"current": 45, "total": 100, "message": "...", "status": "running"}

    Client usage:
        const es = new EventSource(`/api/admin/tasks/${taskId}/progress`)
        es.onmessage = (e) => console.log(JSON.parse(e.data))
    """

    async def event_stream():
        poll_interval = 0.3  # seconds between Redis polls
        timeout = 1800       # 30 minutes max (large audio files)
        elapsed = 0.0

        while elapsed < timeout:
            progress = await get_progress(task_id)

            if progress is None:
                data = json.dumps({
                    "current": 0,
                    "total": 100,
                    "message": "等待任务开始...",
                    "status": "pending",
                })
            else:
                data = json.dumps(progress)

            yield f"data: {data}\n\n"

            if progress and progress.get("status") in ("done", "error"):
                break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if elapsed >= timeout:
            yield f"data: {json.dumps({'status': 'error', 'message': '任务超时'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )