from abc import ABC, abstractmethod
from ..models import Word


class WhisperBackend(ABC):
    """
    Abstract base for whisper backends.
    Each backend must implement transcribe_raw() and return Word list.
    The rest of the pipeline (SentenceSplitter) is backend-agnostic.

    offset_sec: when called on a VAD-sliced audio chunk, all returned
    word timestamps are shifted by this value so they reflect absolute
    positions in the original file.
    """

    @abstractmethod
    def transcribe_raw(
        self,
        wav_path: str,
        language: str,
        offset_sec: float = 0.0,
    ) -> list[Word]:
        """
        Transcribe a 16kHz mono WAV file.
        Returns word-level timestamps as list[Word].

        Args:
            wav_path:   path to 16kHz mono WAV (full file or a slice)
            language:   BCP-47 language code, e.g. "en", "zh"
            offset_sec: seconds to add to every word.start / word.end
                        so that timestamps are absolute in the source file.
                        Pass 0.0 (default) when transcribing the full file.

        All float values must be Python float (not np.float64).
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier for logging."""