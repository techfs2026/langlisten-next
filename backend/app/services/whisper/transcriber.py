"""
WhisperTranscriber: auto-selects backend based on platform.

Detection order:
  1. Apple Silicon (Darwin + arm64) → MlxBackend
  2. NVIDIA GPU available           → FasterWhisperBackend(device=cuda)
  3. Fallback                       → FasterWhisperBackend(device=cpu)

VAD pipeline:
  SileroVAD detects speech segments, then merge_segments() consolidates
  them into chunks ≤ vad_max_chunk_sec (default 25s).

  Merging into larger chunks (vs. keeping 48 tiny segments) means Whisper
  always has enough context to complete sentences — fixing the boundary
  truncation issue where words like "Good morning, World" were being cut
  off at the end of a short VAD slice.

  VAD still provides value: long silences are skipped entirely, reducing
  hallucinations on quiet sections.
"""

from __future__ import annotations

import os
import logging
import platform
import subprocess
import tempfile
from typing import Callable

from .models import Word, TranscribedSegment
from .splitter import SentenceSplitter
from .backends.base import WhisperBackend
from .vad import SileroVAD, SpeechSegment, merge_segments

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


# ── backend auto-detection ────────────────────────────────────────────────────

def _detect_backend(
    model_size: str,
    device: str,
    compute_type: str,
) -> WhisperBackend:
    system = platform.system()
    machine = platform.machine()

    if system == "Darwin" and machine == "arm64":
        try:
            import mlx_whisper  # noqa: F401
            from .backends.mlx import MlxBackend
            logger.info("[Transcriber] Platform: Apple Silicon → MlxBackend")
            return MlxBackend(model_size)
        except ImportError:
            raise RuntimeError(
                "Mac M 系列芯片请安装 mlx-whisper: pip install mlx-whisper\n"
                "不建议在 Mac 上用 faster-whisper，速度差 4-5 倍。"
            )

    if _has_cuda():
        try:
            from .backends.faster import FasterWhisperBackend
            logger.info("[Transcriber] Platform: NVIDIA GPU → FasterWhisperBackend(cuda)")
            return FasterWhisperBackend(model_size, device="cuda", compute_type="float16")
        except Exception as e:
            logger.warning(f"[Transcriber] CUDA init failed: {e}. Falling back to CPU.")

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


# ── audio slicing ─────────────────────────────────────────────────────────────

def _extract_segment_wav(
    src_wav: str,
    start_sec: float,
    end_sec: float,
    tmp_dir: str,
    idx: int,
) -> str:
    out_path = os.path.join(tmp_dir, f"seg_{idx:04d}.wav")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", src_wav,
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-ar", "16000", "-ac", "1",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg slice failed for [{start_sec}-{end_sec}]: "
            f"{result.stderr.decode()}"
        )
    return out_path


# ── main class ────────────────────────────────────────────────────────────────

class WhisperTranscriber:
    """
    Platform-agnostic transcriber with Silero VAD pre-processing.

    Usage:
        t = WhisperTranscriber(model_size="medium")
        segments = t.transcribe("audio.wav", language="en")

    Set use_vad=False to skip VAD and transcribe the full file at once.
    """

    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
        max_seg_sec: float = 12.0,
        soft_break_sec: float = 6.0,
        min_seg_sec: float = 0.5,
        # VAD params
        use_vad: bool = False,
        vad_threshold: float = 0.4,
        vad_min_speech_ms: int = 300,
        vad_min_silence_ms: int = 500,
        vad_speech_pad_ms: int = 200,
        # Max duration per chunk sent to Whisper.
        # Larger = more context for Whisper (fewer cut sentences).
        # Smaller = less memory per chunk.
        # 25s is safe: Whisper's window is 30s, leaving 5s headroom.
        vad_max_chunk_sec: float = 25.0,
    ) -> None:
        self._backend = _detect_backend(model_size, device, compute_type)
        self._splitter = SentenceSplitter(
            max_seg_sec=max_seg_sec,
            soft_break_sec=soft_break_sec,
            min_seg_sec=min_seg_sec,
        )
        self._use_vad = use_vad
        self._vad_max_chunk_sec = vad_max_chunk_sec

        if use_vad:
            self._vad = SileroVAD(
                threshold=vad_threshold,
                min_speech_ms=vad_min_speech_ms,
                min_silence_ms=vad_min_silence_ms,
                speech_pad_ms=vad_speech_pad_ms,
            )
        else:
            self._vad = None

        logger.info(
            f"[Transcriber] Ready. "
            f"backend={self._backend.name} model={model_size} "
            f"vad={'on' if use_vad else 'off'}"
        )

    # ── public API ────────────────────────────────────────────────────────────

    def transcribe(
        self,
        wav_path: str,
        language: str = "en",
        on_progress: ProgressCallback | None = None,
    ) -> list[TranscribedSegment]:

        total_steps = 4 if self._use_vad else 3

        if on_progress:
            on_progress(0, total_steps, "开始转写...")

        # ── Step 1: VAD ───────────────────────────────────────────────────────
        if self._use_vad:
            raw_segments = self._vad.detect(wav_path)

            # Merge short adjacent segments into chunks ≤ vad_max_chunk_sec.
            # This prevents sentence truncation at VAD boundaries: instead of
            # 48 tiny slices, Whisper receives a handful of 10-25s chunks with
            # enough context to complete each sentence naturally.
            speech_segments = merge_segments(raw_segments, max_duration=self._vad_max_chunk_sec)

            logger.info(
                f"[Transcriber] VAD: {len(raw_segments)} raw → "
                f"{len(speech_segments)} merged chunk(s) "
                f"(max {self._vad_max_chunk_sec}s each)."
            )
            if on_progress:
                on_progress(1, total_steps, f"VAD 检测到 {len(speech_segments)} 段语音")
        else:
            speech_segments = None

        # ── Step 2: transcription ─────────────────────────────────────────────
        if on_progress:
            step = 2 if self._use_vad else 1
            on_progress(step, total_steps, "转写中...")

        all_words: list[Word] = self._run_transcription(
            wav_path, language, speech_segments
        )
        logger.info(f"[Transcriber] {len(all_words)} words collected.")

        # ── Step 3: sentence splitting ────────────────────────────────────────
        if on_progress:
            step = 3 if self._use_vad else 2
            on_progress(step, total_steps, "分句处理中...")

        segments = self._splitter.split(all_words)
        for idx, seg in enumerate(segments):
            seg.seq = idx

        logger.info(
            f"[Transcriber] {len(all_words)} words → {len(segments)} segments."
        )

        if on_progress:
            on_progress(total_steps, total_steps, f"完成，共 {len(segments)} 句")

        return segments

    # ── private ───────────────────────────────────────────────────────────────

    def _run_transcription(
        self,
        wav_path: str,
        language: str,
        speech_segments: list[SpeechSegment] | None,
    ) -> list[Word]:
        if speech_segments is None:
            return self._backend.transcribe_raw(wav_path, language, offset_sec=0.0)

        if not speech_segments:
            logger.warning("[Transcriber] VAD returned empty — transcribing full file as fallback.")
            return self._backend.transcribe_raw(wav_path, language, offset_sec=0.0)

        all_words: list[Word] = []

        with tempfile.TemporaryDirectory(prefix="whisper_vad_") as tmp_dir:
            for idx, (start_sec, end_sec) in enumerate(speech_segments):
                logger.debug(
                    f"[Transcriber] Chunk {idx+1}/{len(speech_segments)}: "
                    f"{start_sec:.3f}s – {end_sec:.3f}s "
                    f"({end_sec - start_sec:.1f}s)"
                )
                try:
                    seg_wav = _extract_segment_wav(
                        wav_path, start_sec, end_sec, tmp_dir, idx
                    )
                    words = self._backend.transcribe_raw(
                        seg_wav,
                        language,
                        offset_sec=start_sec,
                    )
                    all_words.extend(words)
                except Exception as exc:
                    logger.error(
                        f"[Transcriber] Chunk {idx} ({start_sec:.3f}-{end_sec:.3f}) "
                        f"failed: {exc}. Skipping."
                    )

        return all_words