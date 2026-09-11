# P1-03d. Функциональные проверки (unit / integration / e2e)

**Для файлов:** `practices/practice_01/tests_unit.md`, `practices/practice_01/tests_integration.md`, `practices/practice_01/tests_e2e.md`

## Промпт

```text
Роль: QA engineer. Читай только practices/practice_01/TRAINING_PR.diff, CASE.md, analysis.md, adr.md. Не менять эти файлы.

Задача: сгенерировать 3 файла — tests_unit.md, tests_integration.md, tests_e2e.md. Каждый — таблица с указанными колонками + блок «Как использовали AI».

Правила кейса: SEC-1, API-1 (>20000 → 413), REL-1 (таймаут 10с → контролируемый ответ без 5xx), OUT-1 (summary + risks≤3{file,line,evidence,risk} + checks), QA-1, OBS-1.

tests_unit.md: колонки Требование/Что проверяем/Вход/Ожидаемый результат/Evidence. Минимум 3 строки: SEC-1 (редактор секретов на «token=…», «BEGIN PRIVATE KEY»), API-1 (валидация длины 20001), OUT-1 (сборщик ответа: risks ≤3, обязательные поля).

tests_integration.md: колонки Связь компонентов/Что может сломаться/Как воспроизводим/Ожидаемый результат/Evidence. Минимум 2 строки: API↔ReviewService↔LLM (валидный diff → 200 + OUT-1); ReviewService↔LLM (задержка/исключение → контролируемый ответ REL-1, не 5xx).

tests_e2e.md: колонки Сценарий/Предусловия/Действие/Наблюдаемый результат/Evidence. Три сценария: позитивный (200 + OUT-1); негативный (>20000 → 413); граничный (ровно 20000 → 200).

Формат: три секции `File: <path>` + полное содержимое. Без Chain of Thought.
```
