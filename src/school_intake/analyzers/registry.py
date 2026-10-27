"""Явный реестр фабрик. Глобального состояния нет: реестр создаётся и передаётся."""

from __future__ import annotations

from collections.abc import Callable

from ..errors import AnalysisFailure, UnknownAnalyzerError
from .base import Analyzer
from .length import LengthAnalyzer
from .template import TemplateAnalyzer

AnalyzerFactory = Callable[[], Analyzer]


class AnalyzerRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, AnalyzerFactory] = {}

    def register(self, name: str, factory: AnalyzerFactory) -> None:
        if not name.strip() or name in self._factories:
            raise AnalysisFailure(
                "Требуется непустое уникальное имя анализатора", field="analyzer_id"
            )
        self._factories[name] = factory

    def create(self, name: str) -> Analyzer:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise UnknownAnalyzerError(
                f"Неизвестный анализатор: {name}", field="analyzer_id"
            ) from exc
        analyzer = factory()  # новый экземпляр при каждом вызове
        if analyzer.analyzer_id != name:
            raise AnalysisFailure("Имя регистрации не совпадает с analyzer_id", field="analyzer_id")
        return analyzer

    def names(self) -> list[str]:
        return sorted(self._factories)


def default_registry() -> AnalyzerRegistry:
    registry = AnalyzerRegistry()
    registry.register("length", LengthAnalyzer)
    registry.register("template", TemplateAnalyzer)
    return registry
