"""JSONL-источник: читает файл построчно и владеет файловым дескриптором."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from ..errors import FormatError
from ..parser import decode_json
from .base import SourceRecord


class JSONLSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.last_closed: bool | None = None  # диагностика: закрыт ли файл после open()

    @contextmanager
    def open(self) -> Iterator[Iterator[SourceRecord]]:
        # Ошибка открытия (OSError) — не ошибка одной записи: пробрасывается как есть.
        handle = self.path.open("r", encoding="utf-8")
        try:
            yield self._records(handle)
        finally:
            handle.close()
            self.last_closed = handle.closed

    @staticmethod
    def _records(handle: TextIO) -> Iterator[SourceRecord]:
        for number, line in enumerate(handle, start=1):
            try:
                raw = decode_json(line)  # пустая строка -> invalid_json, чтение продолжается
            except FormatError as exc:
                yield SourceRecord(number, error=exc)
            else:
                yield SourceRecord(number, raw=raw)
