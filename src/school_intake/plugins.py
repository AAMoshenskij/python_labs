"""Внешние анализаторы через entry points (углубление Core).

Внешний пакет объявляет в своём ``pyproject.toml``::

    [project.entry-points."school_intake.analyzers"]
    custom = "custom_analyzer.plugin:CustomAnalyzer"

Имя entry point обязано совпадать с ``analyzer_id`` (проверяет реестр).
Граница доверия: ``entry.load()`` импортирует и выполняет код пакета, поэтому
механизм подходит для контролируемых расширений, но не для кода студентов.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import EntryPoint, entry_points
from typing import Protocol

from .analyzers.registry import AnalyzerFactory, AnalyzerRegistry
from .errors import PluginLoadError

ENTRY_POINT_GROUP = "school_intake.analyzers"
PLUGIN_API_VERSION = "1"


class EntryPointLike(Protocol):
    @property
    def name(self) -> str: ...

    def load(self) -> object: ...


def discover(group: str = ENTRY_POINT_GROUP) -> Iterable[EntryPoint]:
    return entry_points(group=group)


def load_plugins(
    registry: AnalyzerRegistry, entries: Iterable[EntryPointLike] | None = None
) -> list[str]:
    """Регистрирует фабрики из entry points; возвращает имена. Бросает PluginLoadError."""
    loaded: list[str] = []
    for entry in discover() if entries is None else entries:
        try:
            factory = entry.load()
        except Exception as exc:  # ImportError, AttributeError и ошибки кода плагина
            raise PluginLoadError(
                f"Не удалось загрузить плагин {entry.name!r}: {exc}", field=entry.name
            ) from exc
        if not callable(factory):
            raise PluginLoadError(f"Плагин {entry.name!r} не является фабрикой", field=entry.name)
        registry.register(entry.name, _as_factory(factory))
        loaded.append(entry.name)
    return loaded


def _as_factory(factory: object) -> AnalyzerFactory:
    assert callable(factory)
    return factory
