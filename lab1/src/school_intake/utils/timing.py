"""Типизированный декоратор измерения времени (углубление Core).

``ParamSpec`` сохраняет типы параметров исходной функции, ``TypeVar`` — тип
результата, ``functools.wraps`` — имя, docstring и ``__wrapped__``. Время
записывается в ``finally``, поэтому учитываются и вызовы с исключением; само
исключение и возвращаемое значение не меняются.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class TimingRecorder:
    """Накопитель измерений: ``records[name] -> [секунды, ...]``."""

    records: dict[str, list[float]] = field(default_factory=dict)

    def __call__(self, name: str, seconds: float) -> None:
        self.records.setdefault(name, []).append(seconds)

    def summary(self) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for name, values in sorted(self.records.items()):
            ordered = sorted(values)
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
            result[name] = {
                "calls": float(len(ordered)),
                "total_ms": sum(ordered) * 1000,
                "mean_ms": statistics.fmean(ordered) * 1000,
                "median_ms": statistics.median(ordered) * 1000,
                "p95_ms": p95 * 1000,
                "max_ms": ordered[-1] * 1000,
            }
        return result


def timed(sink: Callable[[str, float], None]) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """``@timed(recorder)``: передаёт в ``sink(имя, секунды)`` время каждого вызова."""

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                sink(function.__qualname__, perf_counter() - start)

        return wrapped

    return decorator
