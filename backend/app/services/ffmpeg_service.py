"""
FFmpeg utilities for audio preprocessing.

Responsibilities:
- Get audio duration
- Convert any audio format to 16kHz mono WAV for Whisper
- Run in a thread (CPU-bound, must not block the async event loop)
"""

import asyncio
import logging
from pathlib import Path

import ffmpeg

logger = logging.getLogger(__name__)


def _get_duration(path: str) -> float:
    """Synchronous: probe audio duration via ffmpeg."""
    try:
        probe = ffmpeg.probe(path)
        return float(probe["format"]["duration"])
    except Exception as e:
        logger.warning(f"Could not get duration for {path}: {e}")
        return 0.0


def _convert_to_wav(src: str, dst: str) -> None:
    """
    Synchronous: convert any audio to 16kHz mono WAV.
    Required format for Whisper and Silero VAD.
    """
    (
        ffmpeg.input(src)
        .output(dst, ar=16000, ac=1, acodec="pcm_s16le")
        .overwrite_output()
        .run(quiet=True)
    )


async def get_duration(path: str) -> float:
    """Async wrapper — runs ffprobe in a thread pool."""
    return await asyncio.to_thread(_get_duration, path)


async def convert_to_wav(src: str, dst: str) -> None:
    """Async wrapper — runs ffmpeg conversion in a thread pool."""
    logger.info(f"Converting {src} → {dst}")
    await asyncio.to_thread(_convert_to_wav, src, dst)
    logger.info(f"Conversion complete: {dst}")