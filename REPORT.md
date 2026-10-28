# Отчёт по ЛР 1

**Траектория:** Python Core. **Уровень:** основной + углубление Core (entry points, типизированный декоратор времени).

## Выполненные требования

| Требование | Где реализовано | Чем проверено |
|---|---|---|
| Пакет в src-layout, установка в чистое окружение | `pyproject.toml`, `src/school_intake` | `pip install .` в новом venv |
| Модель Submission, неизменяемые версии, устойчивый хеш | `models.py`, `hashing.py` | `tests/test_acceptance.py` |
| Разбор JSON, валидация полей, зоны, AI-декларации; вход не меняется | `parser.py`, `validation.py` | `tests/test_parsing.py` (параметризованные случаи, сравнение с копией) |
| Ошибка с code, field, message; формат / схема / конфликт | `errors.py` | `tests/test_parsing.py`, `tests/test_acceptance.py` |
| duplicate возвращает принятую сдачу; conflict не перезаписывает | `service.py` | `tests/test_acceptance.py` |
| CLI import, частичный успех, номер строки | `cli.py`, `importer.py` | `tests/test_import_cli.py` |
| Контракт Analyzer, analyzer_id / analyzer_version / config_hash | `analyzers/base.py`, `reporting.py` | `tests/test_analyzers.py` |
| LengthAnalyzer, TemplateAnalyzer; evidence по исходным номерам строк | `analyzers/length.py`, `template.py` | `tests/test_analyzers.py` |
| Два источника, закрытие файла при ошибке и раннем выходе | `sources/` | `tests/test_sources.py` |
| Реестр фабрик, сервис без ветвления по классам | `analyzers/registry.py`, `analysis_service.py` | `tests/test_analyzers.py` (в том числе проверка исходника сервиса) |
| Ошибка анализатора, проверка результата на границе | `analysis_service.py`, `reporting.py` | `tests/test_analyzers.py` |
| Третий анализатор без изменения сервиса | `analyzers/declaration.py` | `tests/test_analyzers.py`, `scripts/defense_demo.py` |
| Углубление: entry points | `plugins.py` | `tests/test_plugins.py` (установленный dist-info, дубль имени, ошибка импорта) |
| Углубление: декоратор времени | `utils/timing.py` | `tests/test_timing.py`, `scripts/measure.py` |

Протокол и наследование: `Protocol` задаёт структуру (подходит любой класс с нужными методами, без общего предка), ABC — номинальную иерархию с обязательными абстрактными методами. Совместимость сигнатуры не гарантирует закрытие файла или корректность отчёта, поэтому поведение проверяют контрактные тесты.

## Команды проверки

```powershell
pip install -e ".[dev]"
pytest
mypy
ruff check .
school-intake import data\submissions.jsonl
school-intake import data\invalid_submissions.jsonl
school-intake analyze data\submissions.jsonl --assignments data\assignments.json
python scripts\defense_demo.py
python scripts\measure.py 3000
```

Windows 11, Python 3.15.2: 158 тестов проходят, `mypy` (strict) и `ruff check` без замечаний. Корпус из 12 сдач даёт 12 accepted, затем 12 duplicate и 24 отчёта.

## Измерения

Замер из `scripts/measure.py 3000` (12 сдач × 2 анализатора × 3000 кругов = 72 000 вызовов `AnalysisService.run`). Среда: Windows 11 (10.0.26200), Python 3.15.2.

| Показатель | Значение |
|---|---|
| Импорт корпуса из 12 сдач | 1,6 мс |
| `service.run` без декоратора | 106,2 мкс на вызов |
| `service.run` с `@timed` на `analyze` | 116,2 мкс на вызов |
| Накладные расходы декоратора | ≈ 10,0 мкс на вызов |
| `LengthAnalyzer.analyze`: среднее / медиана / p95 | 85 / 81 / 93 мкс |
| `TemplateAnalyzer.analyze`: среднее / медиана / p95 | 75 / 74 / 83 мкс |

Объяснение. Реестр создаёт новый экземпляр анализатора при каждом `create()`, поэтому в замере декоратор оборачивает метод заново при каждом вызове сервиса. Накладные расходы включают создание замыкания, два вызова `perf_counter` и запись в накопитель, а не только само измерение. При долгоживущем экземпляре они были бы меньше. Максимумы (несколько мс) — редкие паузы системы, поэтому для оценки типичного времени использованы медиана и p95. Для корпуса из 12 коротких сдач время анализа пренебрежимо мало по сравнению с чтением файла; вывод о масштабировании на большие работы по этим данным делать нельзя.

Разброс. Повторный запуск на той же машине дал 90,9 мкс без декоратора и 82,4 мкс с ним, то есть разницу −8,5 мкс; `LengthAnalyzer` / `TemplateAnalyzer` — 60 / 53 мкс в среднем. Декоратор не может ускорять вызов: накладные расходы порядка 10 мкс меньше шума измерения на Windows (изменение частоты процессора, фоновые процессы). Скрипт делает по одному прогону с декоратором и без, поэтому знак разницы между запусками случаен. Вывод: накладные расходы `@timed` на этом объёме пренебрежимо малы; для точной оценки нужны несколько чередующихся повторов и медиана.

## Известные ограничения

- In-memory репозиторий; `get` + `add` не атомарны при нескольких потоках (ЛР 3).
- `data/assignments.json` и `data/invalid_submissions.jsonl` составлены по описанию из ноутбука курса; `submissions.jsonl` взят из ноутбука.
- Шаблон ищется точным совпадением блока строк; нечёткое сходство и AST-анализ не выполняются.
- Entry points выполняют код установленного пакета; механизм не изолирует плагин.
- Измерения зависят от машины и Python.
