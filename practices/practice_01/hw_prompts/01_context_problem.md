# P1-03a. Контекст и проблема

**Для файлов:** `practices/practice_01/context.md`, `practices/practice_01/problem.md`

## Промпт

```text
Роль: SDLC-аналитик и technical writer. Читай только practices/practice_01/TRAINING_PR.diff, CASE.md, README.md. Не менять эти файлы.

Задача: сгенерировать содержимое двух файлов — context.md и problem.md.

Context Pack (из CASE.md): SEC-1 (маскирование секретов), API-1 (>20000 → 413), REL-1 (таймаут 10с, без 5xx), OUT-1 (summary + risks≤3{file,line,evidence,risk} + checks), SCOPE-1 (только советы), QA-1 (риск только с evidence), OBS-1 (лог только request_id/duration/status). Не включай правила про snake_case и i18n.

context.md: Summary из 2 предложений; таблица 5 AS IS-вопросов + источник/допущение; Context Pack (Факты, Формат, Ограничения, Хороший/Плохой пример, Что неизвестно); блок «Как использовали AI».

problem.md: пользователь / ситуация / что сейчас / почему мешает / что не входит; таблица «Метрики» — минимум 3 измеримые метрики, привязанные к правилам (без VTG/IRR/CSAT); «Почему изменение метрики подтвердит решение»; блок «Как использовали AI».

Формат: две секции `File: <path>` + полное содержимое. Без Chain of Thought.
```
