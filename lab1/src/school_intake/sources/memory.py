"""In-memory источник: тот же контракт, что у JSONLSource."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from contextlib import contextmanager

from .base import SourceRecord


class InMemorySource:
    def __init__(self, values: list[dict[str, object]]) -> None:
        self._values = copy.deepcopy(values)

    @contextmanager
    def open(self) -> Iterator[Iterator[SourceRecord]]:
        def records() -> Iterator[SourceRecord]:
            for number, raw in enumerate(self._values, start=1):
                # копия: потребитель не может изменить исходную коллекцию
                yield SourceRecord(number, copy.deepcopy(raw))

        yield records()
