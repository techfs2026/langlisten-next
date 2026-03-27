"""
MLX backend: Apple Silicon only, uses Metal GPU via mlx-whisper.
~5-8x realtime on M-series chips.

Requires: pip install mlx-whisper
"""

import logging
from ..models import Word
from .base import WhisperBackend

logger = logging.getLogger(__name__)

MLX_MODEL_MAP = {
    "tiny":     "mlx-community/whisper-tiny-mlx",
    "base":     "mlx-community/whisper-base-mlx",
    "small":    "mlx-community/whisper-small-mlx",
    "medium":   "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


class MlxBackend(WhisperBackend):

    def __init__(self, model_size: str) -> None:
        self.model_name = MLX_MODEL_MAP.get(
            model_size,
            f"mlx-community/whisper-{model_size}-mlx",
        )
        logger.info(f"[MLX] model={self.model_name}")

    @property
    def name(self) -> str:
        return "mlx"

    def transcribe_raw(self, wav_path: str, language: str) -> list[Word]:
        import mlx_whisper

        result = mlx_whisper.transcribe(
            wav_path,
            path_or_hf_repo=self.model_name,
            language=language,
            word_timestamps=True,
            verbose=False,
        )

        words: list[Word] = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append(Word(
                    word=w["word"],
                    start=float(round(w["start"], 3)),
                    end=float(round(w["end"], 3)),
                    probability=float(round(w.get("probability", 1.0), 4)),
                ))
        return words