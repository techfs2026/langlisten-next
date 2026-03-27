"""
WhisperTranscriber: auto-selects backend based on platform.

Detection order:
  1. Apple Silicon (Darwin + arm64) → MlxBackend
  2. NVIDIA GPU available           → FasterWhisperBackend(device=cuda)
  3. Fallback                       → FasterWhisperBackend(device=cpu)

No manual configuration needed.
"""

from __future__ import annotations

import platform
import logging
from typing import Callable

from .models import Word, TranscribedSegment
from .splitter import SentenceSplitter
from .backends.base import WhisperBackend

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


def _detect_backend(
    model_size: str,
    device: str,
    compute_type: str,
) -> WhisperBackend:
    """
    Auto-detect the best available backend for the current platform.
    Called once at WhisperTranscriber instantiation.
    """
    system = platform.system()
    machine = platform.machine()

    # ── Apple Silicon ─────────────────────────────────────────────────────────
    if system == "Darwin" and machine == "arm64":
        try:
            import mlx_whisper  # noqa: F401
            from .backends.mlx import MlxBackend
            logger.info("[Transcriber] Platform: Apple Silicon → MlxBackend")
            return MlxBackend(model_size)
        except ImportError:
            logger.warning(
                "[Transcriber] Apple Silicon detected but mlx-whisper not installed. "
                "Run: pip install mlx-whisper. Falling back to faster-whisper."
            )

    # ── NVIDIA GPU ────────────────────────────────────────────────────────────
    if _has_cuda():
        try:
            from .backends.faster import FasterWhisperBackend
            logger.info("[Transcriber] Platform: NVIDIA GPU → FasterWhisperBackend(cuda)")
            return FasterWhisperBackend(model_size, device="cuda", compute_type="float16")
        except Exception as e:
            logger.warning(f"[Transcriber] CUDA detected but failed to init: {e}. Falling back to CPU.")

    # ── CPU fallback ──────────────────────────────────────────────────────────
    from .backends.faster import FasterWhisperBackend
    logger.info(f"[Transcriber] Platform: CPU → FasterWhisperBackend(cpu, {compute_type})")
    return FasterWhisperBackend(model_size, device="cpu", compute_type=compute_type)


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        pass
    try:
        import ctranslate2
        return "cuda" in ctranslate2.get_supported_compute_types("cuda")
    except Exception:
        return False


class WhisperTranscriber:
    """
    Platform-agnostic transcriber. Auto-selects the best backend.

    Usage:
        t = WhisperTranscriber(model_size="medium")
        segments = t.transcribe("audio.wav", language="en")
    """

    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
        max_seg_sec: float = 12.0,
        soft_break_sec: float = 6.0,
        min_seg_sec: float = 0.5,
    ) -> None:
        self._backend = _detect_backend(model_size, device, compute_type)
        self._splitter = SentenceSplitter(
            max_seg_sec=max_seg_sec,
            soft_break_sec=soft_break_sec,
            min_seg_sec=min_seg_sec,
        )
        logger.info(
            f"[Transcriber] Ready. backend={self._backend.name} model={model_size}"
        )

    def transcribe(
        self,
        wav_path: str,
        language: str = "en",
        on_progress: ProgressCallback | None = None,
    ) -> list[TranscribedSegment]:
        if on_progress:
            on_progress(0, 3, "开始转写...")

        # Step 1: backend-specific raw transcription
        all_words: list[Word] = self._backend.transcribe_raw(wav_path, language)
        logger.info(f"[Transcriber] {len(all_words)} words collected.")

        if on_progress:
            on_progress(1, 3, "收集转写结果...")

        # Step 2: reassemble into sentences (backend-agnostic)
        if on_progress:
            on_progress(2, 3, "分句处理中...")

        segments = self._splitter.split(all_words)
        for idx, seg in enumerate(segments):
            seg.seq = idx

        logger.info(
            f"[Transcriber] {len(all_words)} words → {len(segments)} segments."
        )

        if on_progress:
            on_progress(3, 3, f"完成，共 {len(segments)} 句")

        return segments