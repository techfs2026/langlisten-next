"""
Faster-Whisper backend: NVIDIA GPU or CPU via CTranslate2.

Requires: pip install faster-whisper
Config:
  device=cuda, compute_type=float16  → NVIDIA GPU (recommended)
  device=cpu,  compute_type=int8     → CPU fallback
"""

import logging
from ..models import Word
from .base import WhisperBackend

logger = logging.getLogger(__name__)


class FasterWhisperBackend(WhisperBackend):

    def __init__(self, model_size: str, device: str, compute_type: str) -> None:
        from faster_whisper import WhisperModel
        logger.info(
            f"[FasterWhisper] model={model_size} "
            f"device={device} compute_type={compute_type}"
        )
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    @property
    def name(self) -> str:
        return "faster_whisper"

    def transcribe_raw(self, wav_path: str, language: str) -> list[Word]:
        segments_iter, _ = self._model.transcribe(
            wav_path,
            language=language,
            word_timestamps=True,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                min_speech_duration_ms=200,
            ),
        )

        words: list[Word] = []
        for seg in segments_iter:
            if not seg.words:
                continue
            for w in seg.words:
                words.append(Word(
                    word=w.word,
                    start=float(round(w.start, 3)),
                    end=float(round(w.end, 3)),
                    probability=float(round(w.probability, 4)),
                ))
        return words