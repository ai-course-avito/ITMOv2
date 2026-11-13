# Style Guide (Python) — Практика 3

Источник: PEP 8 — Style Guide for Python Code (версия на docs: https://peps.python.org/pep-0008/)

Применение: Python-файлы практики 3 (например, practices/practice_03/**/*.py)

Правила (выжимка 4 шт.)

1) Имена функций и переменных — lowercase_with_underscores
- Ссылка: https://peps.python.org/pep-0008/#function-and-variable-names
- Пример в репозитории: practices/practice_03/check_pptx.py:16 — `def main():`

2) Импорты — в начале файла; одна строка — один импорт; группировать: stdlib / third‑party / local
- Ссылка: https://peps.python.org/pep-0008/#imports
- Пример в репозитории: practices/practice_03/check_pptx.py:1-3 — `import sys`, `import zipfile`, `from io import BytesIO`

3) Отступы — 4 пробела на уровень; табы не использовать
- Ссылка: https://peps.python.org/pep-0008/#indentation
- Пример в репозитории: practices/practice_03/make_md.py:18-46 — тело функций с отступами по 4 пробела

4) Пробелы вокруг операторов и после запятых — соблюдать; избегать лишних пробелов
- Ссылка: https://peps.python.org/pep-0008/#other-recommendations
- Пример в репозитории: practices/practice_03/check_pptx.py:38 — `for i, (exp, got) in enumerate( ... ):`
