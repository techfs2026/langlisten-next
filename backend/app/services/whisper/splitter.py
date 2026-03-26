"""
SentenceSplitter: reassemble word-level timestamps into complete sentences.

All timestamps are cast to Python float (not np.float64) before returning,
so SQLAlchemy / psycopg2 can handle them without issues.
"""

from __future__ import annotations

import re
import logging
from .models import Word, TranscribedSegment

logger = logging.getLogger(__name__)

_STRONG_BREAK = re.compile(r"[.!?…]+$")
_SOFT_BREAK = re.compile(r"[,;:]+$")


class SentenceSplitter:
    """
    Pure in-memory transformation: list[Word] -> list[TranscribedSegment].
    No I/O, no external dependencies.
    """

    def __init__(
        self,
        max_seg_sec: float = 12.0,
        soft_break_sec: float = 6.0,
        min_seg_sec: float = 0.5,
    ) -> None:
        self.max_seg_sec = max_seg_sec
        self.soft_break_sec = soft_break_sec
        self.min_seg_sec = min_seg_sec

    def split(self, words: list[Word]) -> list[TranscribedSegment]:
        if not words:
            return []
        groups = self._group_words(words)
        groups = self._merge_short(groups)
        return self._to_segments(groups)

    # ── private ───────────────────────────────────────────────────────────────

    def _group_words(self, words: list[Word]) -> list[list[Word]]:
        groups: list[list[Word]] = []
        current: list[Word] = []

        for word in words:
            current.append(word)
            text = word.word.strip()
            duration = current[-1].end - current[0].start

            if _STRONG_BREAK.search(text):
                groups.append(current)
                current = []
            elif _SOFT_BREAK.search(text) and duration >= self.soft_break_sec:
                groups.append(current)
                current = []
            elif duration >= self.max_seg_sec:
                groups.append(current)
                current = []

        if current:
            groups.append(current)

        return groups

    def _merge_short(self, groups: list[list[Word]]) -> list[list[Word]]:
        if len(groups) <= 1:
            return groups

        merged: list[list[Word]] = []
        for i, group in enumerate(groups):
            duration = group[-1].end - group[0].start
            if duration < self.min_seg_sec and i + 1 < len(groups):
                groups[i + 1] = group + groups[i + 1]
            elif duration < self.min_seg_sec and merged:
                merged[-1] = merged[-1] + group
            else:
                merged.append(group)
        return merged

    def _to_segments(self, groups: list[list[Word]]) -> list[TranscribedSegment]:
        segments: list[TranscribedSegment] = []
        for i, group in enumerate(groups):
            text = "".join(w.word for w in group).strip()
            if not text:
                continue
            segments.append(TranscribedSegment(
                seq=i,
                # cast to Python float — faster-whisper returns np.float64
                start_time=float(round(group[0].start, 3)),
                end_time=float(round(group[-1].end, 3)),
                text=text,
                words=group,
            ))
        return segments