"""
Celery task: transcribe audio and persist subtitles.

Fully synchronous — no async/await anywhere in this file.
Celery workers are sync processes; mixing asyncio causes event loop conflicts.

DB writes use a sync SQLAlchemy session (psycopg2).
Redis writes use the sync Redis client.
"""

import logging
import tempfile
from pathlib import Path

from celery import shared_task
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.worker import celery_app
from app.core.config import settings
from app.core.redis import set_progress_sync

logger = logging.getLogger(__name__)


def _get_sync_engine():
    """Create a sync SQLAlchemy engine for use inside Celery tasks."""
    return create_engine(
        settings.database_url_sync,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
    )


@celery_app.task(bind=True, name="tasks.transcribe_audio")
def transcribe_audio(self, material_id: int, language: str = "en"):
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting transcription for material_id={material_id}")

    engine = _get_sync_engine()

    try:
        _do_transcribe(task_id, material_id, language, engine)
    except Exception as e:
        logger.exception(f"[Task {task_id}] Failed: {e}")
        set_progress_sync(task_id, 0, 100, f"失败: {e}", status="error")
        _set_material_status(engine, material_id, "pending")
        raise
    finally:
        engine.dispose()


def _do_transcribe(task_id: str, material_id: int, language: str, engine):
    from app.models.material import AudioMaterial
    from app.models.subtitle import Subtitle
    from app.services.whisper import WhisperTranscriber
    import subprocess

    # ── Step 1: mark as transcribing ─────────────────────────────────────────
    set_progress_sync(task_id, 0, 100, "准备转写...")
    with Session(engine) as db:
        material = db.get(AudioMaterial, material_id)
        if not material:
            raise ValueError(f"Material {material_id} not found")
        file_path = material.file_path
        material.status = "transcribing"
        db.commit()

    # ── Step 2: convert to WAV ────────────────────────────────────────────────
    set_progress_sync(task_id, 2, 100, "音频格式转换中...")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-ar", "16000", "-ac", "1", "-acodec", "pcm_s16le",
                wav_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")

        # ── Step 3: transcribe ────────────────────────────────────────────────
        def on_progress(current: int, total: int, message: str):
            # transcriber reports 0-3 steps, map to 5-95%
            pct = 5 + int(90 * current / total) if total > 0 else 5
            set_progress_sync(task_id, pct, 100, message)
            logger.info(f"[Task {task_id}] {pct}% {message}")

        transcriber = WhisperTranscriber(
            model_size=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        segments = transcriber.transcribe(
            wav_path,
            language=language,
            on_progress=on_progress,
        )

        # ── Step 4: persist subtitles ─────────────────────────────────────────
        set_progress_sync(task_id, 96, 100, "写入数据库...")
        with Session(engine) as db:
            db.execute(delete(Subtitle).where(Subtitle.material_id == material_id))
            db.flush()

            for seg in segments:
                db.add(Subtitle(
                    material_id=material_id,
                    seq=seg.seq,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    text=seg.text,
                    is_verified=False,
                ))

            material = db.get(AudioMaterial, material_id)
            material.status = "transcribed"
            db.commit()

        set_progress_sync(task_id, 100, 100, f"转写完成，共 {len(segments)} 句", status="done")
        logger.info(f"[Task {task_id}] Done. {len(segments)} segments.")

    finally:
        Path(wav_path).unlink(missing_ok=True)


def _set_material_status(engine, material_id: int, status: str):
    from app.models.material import AudioMaterial
    with Session(engine) as db:
        material = db.get(AudioMaterial, material_id)
        if material:
            material.status = status
            db.commit()