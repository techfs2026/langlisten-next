"""
WhisperTranscriber: transcription orchestration.

Key design change from original:
  Instead of calling model.transcribe() per VAD segment (slow — N model calls),
  we call it ONCE on the full audio with word_timestamps=True,
  then use SentenceSplitter to reassemble words into complete sentences.

  VAD is still used but only to filter silence from the word list,
  not as clip boundaries for separate model calls.

Pipeline:
  1. faster-whisper  → transcribe full WAV once, get word-level timestamps
  2. SileroVAD       → detect speech segments (used to filter stray words in silence)
  3. SentenceSplitter → reassemble words into complete sentences
"""

from __future__ import annotations

import logging
from typing import Callable

from .models import Word, TranscribedSegment
from .splitter import SentenceSplitter

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


class WhisperTranscriber:
    """
    Self-contained transcription module.

    Usage:
        t = WhisperTranscriber(model_size="medium")
        segments = t.transcribe(
            "audio.wav",
            language="en",
            on_progress=lambda cur, tot, msg: print(f"{cur}/{tot} {msg}"),
        )
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
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._splitter = SentenceSplitter(
            max_seg_sec=max_seg_sec,
            soft_break_sec=soft_break_sec,
            min_seg_sec=min_seg_sec,
        )

    def transcribe(
        self,
        wav_path: str,
        language: str = "en",
        on_progress: ProgressCallback | None = None,
    ) -> list[TranscribedSegment]:
        """
        Transcribe a 16kHz mono WAV file in a single model call.

        Args:
            wav_path:    Path to 16kHz mono WAV
            language:    Language code ("en", "zh", etc). None = auto-detect.
            on_progress: Optional callback(current, total, message).

        Returns:
            Time-sorted TranscribedSegment list, seq starting at 0.
        """
        self._ensure_model_loaded()

        if on_progress:
            on_progress(0, 3, "开始转写...")

        # Step 1: single pass transcription with word timestamps
        logger.info(f"[Transcriber] Transcribing: {wav_path}")
        segments_iter, info = self._model.transcribe(
            wav_path,
            language=language,
            word_timestamps=True,
            beam_size=5,
            vad_filter=True,                        # built-in VAD to skip silence
            vad_parameters=dict(
                min_silence_duration_ms=500,
                min_speech_duration_ms=200,
            ),
        )

        if on_progress:
            on_progress(1, 3, "收集转写结果...")

        # collect all words — consume the generator fully
        all_words: list[Word] = []
        for seg in segments_iter:
            if not seg.words:
                continue
            for w in seg.words:
                all_words.append(Word(
                    word=w.word,
                    start=float(round(w.start, 3)),   # cast np.float64 → float
                    end=float(round(w.end, 3)),
                    probability=float(round(w.probability, 4)),
                ))

        logger.info(f"[Transcriber] {len(all_words)} words collected.")

        if on_progress:
            on_progress(2, 3, "分句处理中...")

        # Step 2: reassemble words into complete sentences
        segments = self._splitter.split(all_words)

        for idx, seg in enumerate(segments):
            seg.seq = idx

        logger.info(f"[Transcriber] {len(all_words)} words → {len(segments)} segments.")

        if on_progress:
            on_progress(3, 3, f"完成，共 {len(segments)} 句")

        return segments

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        logger.info(
            f"[Transcriber] Loading model: {self.model_size} "
            f"device={self.device} compute_type={self.compute_type}"
        )
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        logger.info("[Transcriber] Model ready.")