# python_labs

Лабораторные работы по Python. Каждая работа — отдельный проект в своей папке
со своими `pyproject.toml`, `README.md`, `REPORT.md` и `AI_USAGE.md`.

| Работа | Папка | Теги | Описание |
|---|---|---|---|
| ЛР 1 | [lab1](lab1/) | `lab-1-stage-a`, `lab-1` | Приём работ и расширяемые анализаторы (Python Core) |

Промежуточный коммит работы N отмечается тегом `lab-N-stage-a`, итоговый — `lab-N`.

Запуск работы — по инструкции в её `README.md`, из папки работы:

```powershell
cd lab1
pip install -e ".[dev]"
pytest
```
