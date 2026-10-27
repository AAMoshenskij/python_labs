# school-intake — ЛР 1: приём работ и расширяемые анализаторы

Траектория **Python Core**, уровень: основной + углубление (entry points и типизированный декоратор времени).
Зависимостей времени выполнения нет, только стандартная библиотека. Нужен **Python 3.12+** (`python --version`).

## Установка

Чистое окружение (Windows PowerShell):

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # только если PowerShell блокирует activate
.venv\Scripts\activate
pip install .                  # проверка обычной установки
pip install -e ".[dev]"        # для разработки: pytest, ruff, mypy
```

## Запуск

```powershell
# импорт: JSON с accepted / duplicate / errors (у ошибок есть line_no, code, field, message)
school-intake import data\submissions.jsonl
school-intake import data\invalid_submissions.jsonl

# импорт + анализаторы length и template
school-intake analyze data\submissions.jsonl --assignments data\assignments.json

# сценарий защиты и замеры
python scripts\defense_demo.py
python scripts\measure.py 3000
```

Коды завершения: `0` — успех; `1` — ошибки отдельных строк (корректные записи приняты); `2` — источник недоступен.
JSON результата — в stdout, диагностика — в stderr. Состояние in-memory исчезает вместе с процессом.

## Проверки

```powershell
pytest
mypy
ruff check .
```

## Структура

```
src/school_intake/
  errors.py          DomainError(code, field, message): FormatError / SchemaError / UnsupportedVersionError / ConflictError; AnalysisFailure
  models.py          AIDeclaration, Submission, Assignment (frozen dataclass)
  validation.py      вся проверка схемы; возвращает новый Submission, вход не меняет
  parser.py          строгий разбор JSON (без повторов ключей и NaN) отдельно от схемы
  hashing.py         SHA-256 от канонического JSON
  repository.py      Protocol SubmissionRepository + InMemorySubmissionRepository
  service.py         SubmissionService: accepted / duplicate / ConflictError
  sources/           Protocol SubmissionSource; JSONLSource и InMemorySource (open() — контекстный менеджер)
  importer.py        импорт источника через сервис, частичный успех
  analyzers/         модели отчёта, Protocol Analyzer, validate_report, Length / Template / Declaration, реестр фабрик
  analysis_service.py  центральный сервис: выбор по реестру, проверка результата плагина на границе
  plugins.py         внешние анализаторы через entry points (группа school_intake.analyzers)
  utils/timing.py    @timed(recorder): ParamSpec + TypeVar + functools.wraps
  assignments.py     загрузка assignments.json
  cli.py             import и analyze
tests/               parsing, acceptance, sources (контракт), import/CLI, analyzers (контракт), plugins, timing
scripts/             measure.py (замеры), defense_demo.py (сценарий защиты)
data/                submissions.jsonl, invalid_submissions.jsonl, assignments.json
```

## Принятые политики

- Схема версии 1: все девять полей обязательны; неизвестные поля, в том числе внутри `ai_declaration`, отклоняются; `bool` вместо числа и строка `"false"` вместо bool отклоняются; при `used=true` нужны непустые `tool` и `purpose`; хотя бы одно из `text` и `code` непустое.
- Исходные `text`, `code` и `submitted_at` сохраняются без изменений (`strip()` — только для проверки), поэтому одинаковый момент времени в другом представлении даёт другой хеш.
- Хеш сдачи включает все поля, в том числе идентификаторы. Одинаковый код разных студентов — разные хеши.
- Пустая физическая строка JSONL — ошибка `invalid_json`; чтение продолжается. Ошибка открытия файла — не ошибка записи (код `2`).
- Шаблон ищется как точный блок строк в `code` (без нормализации пробелов); нечёткое сходство не проверяется.
- `score` во всех отчётах ЛР 1 равен `None`: обоснованной метрики качества нет.
- Анализатор `declaration` (третий) нарочно не входит в реестр по умолчанию: на защите он подключается регистрацией, `AnalysisService` не меняется.

## Происхождение данных

`data/submissions.jsonl` — 12 сдач из демонстрационного ноутбука курса (ячейка с `PUBLIC_SUBMISSIONS`). `data/assignments.json` и `data/invalid_submissions.jsonl` составлены по описанию из ноутбука (одно задание `assignment-01`; по одной строке на каждый тип ошибки). Если у вас есть официальные версии, замените ими эти два файла.

## Внешние анализаторы (entry points)

В пакете плагина:

```toml
[project.entry-points."school_intake.analyzers"]
custom = "custom_analyzer.plugin:CustomAnalyzer"
```

Имя entry point обязано совпадать с `analyzer_id`. `school-intake analyze` загружает установленные плагины (отключается `--no-plugins`). `entry.load()` выполняет код пакета, поэтому механизм подходит для контролируемых расширений, но не для кода студентов. Версия API плагина: `1` (`plugins.PLUGIN_API_VERSION`).

## Известные ограничения

- Репозиторий in-memory; `get` + `add` не атомарны для нескольких потоков или процессов (конкурентность — ЛР 3).
- Проверка результата плагина защищает от неверного отчёта, но не от вредоносного кода в процессе.
- Код студентов не запускается.
