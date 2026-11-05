---
name: test-runner
description: Run unified project tests for practice_04 and collect logs
---

Когда использовать:
- После правок в `practices/practice_04/src` или тестах.
- Для быстрой локальной проверки без лишних шагов.

Пошаговая процедура:
1. Запустить команду `bash practices/practice_04/skills/test-runner/scripts/run.sh`.
2. Скрипт вызывает `bash practices/practice_04/scripts/check.sh` и сохраняет вывод в `practices/practice_04/evidence/03-skill-run.log`.
3. Проверить код возврата. 0 — успешно, иначе — падение тестов.

Границы (что нельзя):
- Не изменять тесты для получения зелёного статуса.
- Не модифицировать файлы вне `practices/practice_04`.

Проверка и ожидаемый результат:
- Команда: `bash practices/practice_04/skills/test-runner/scripts/run.sh`.
- Exit code: 0 при прохождении тестов; ненулевой при падении.
- В логе ожидается строка без tracebacks при успехе.

Что вернуть:
- Путь к логу `practices/practice_04/evidence/03-skill-run.log`.
- Краткое резюме: количество тестов и статус.
