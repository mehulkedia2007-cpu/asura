"""Incremental sentence boundaries; unfinished tails stay buffered for verification."""

import re


class Sentences:
    def __init__(self) -> None:
        self.pending = ""

    def push(self, text: str, *, final: bool = False) -> list[str]:
        self.pending += text
        parts = re.split(r"(?<=[.!?।])\s+|\n+", self.pending)
        self.pending = parts.pop()
        if final and self.pending.strip():
            parts.append(self.pending)
            self.pending = ""
        return [part.strip() for part in parts if part.strip()]
