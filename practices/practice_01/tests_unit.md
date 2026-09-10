# Unit-проверки

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| SEC-1 | Редактор распознаёт токен и пароль | Diff с `TOKEN=test-token` и `password=hunter2` | Значения заменены на `[REDACTED]`; остальной diff сохранён | `test_redactor_replaces_token_and_password`; ассерты по строке результата |
| SEC-1 | Редактор распознаёт блок приватного ключа | Diff с синтетическим `BEGIN PRIVATE KEY` | Весь секретный блок отсутствует, на его месте `[REDACTED]` | `test_redactor_replaces_private_key_block` |
| SEC-1 | Обычный код не редактируется | Diff без секретов | Результат равен входу | `test_redactor_keeps_safe_diff` |
| REL-1 | Сервис задаёт timeout внешнему вызову | Допустимый diff и fake LLM | В адаптер передано ограничение 10 секунд | `test_review_uses_ten_second_timeout` |
| REL-1 | Исключение/timeout нормализуется | Fake LLM выбрасывает timeout или ошибку | Получен контролируемый доменный результат, исключение не выходит наружу | `test_review_converts_llm_failure_to_controlled_result` |
| OUT-1 | Валидатор результата принимает контракт | `summary`, 0–3 корректных риска, `checks` | Результат принят без изменения обязательных полей | `test_output_accepts_valid_contract` |
| OUT-1, QA-1 | Валидатор отбрасывает лишние и недоказанные риски | 4 риска; один без `evidence` | Не более 3 рисков, каждый содержит `file`, `line`, `evidence`, `risk` | `test_output_limits_and_requires_evidence` |
| OBS-1 | Структурный лог не содержит payload | request_id, diff и ответ fake LLM | В записи есть request_id, длительность, статус; нет diff/ответа | `test_log_contains_metadata_only` |

Планируемый запуск после реализации: `pytest -q tests/unit`.

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-06.
- Что проверили и исправили сами: тесты ограничены поведением отдельных компонентов; использованы только синтетические секреты, а точные имена тестов помечены как планируемый evidence до появления реализации.
