# Журнал экспериментов Практики 2

- Выбранный слабый артефакт Практики 1: prompts.md — раздел «P1-02 Result (OUT-1)» (JSON-ответ AI-агента).
- Что в нём нужно улучшить: удалить или пометить галлюцинации и неподтверждённые риски, усилить evidence (file/line/fragment) и checks, отделить подтверждённые риски от открытых вопросов.
- Как поймём, что изменение полезно: каждый риск подтверждён diff/правилами (QA‑1); спорные утверждения вынесены в «Открытые вопросы»; checks воспроизводимы.

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | `prompts.md` (P1‑02 Result, предложение) | Переписали JSON: добавили evidence и checks; спорные пункты перенесли в «Открытые вопросы» | Сопоставили с `TRAINING_PR.diff`, `context.md` | Любые пункты без источников |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | `prompts.md` (P1‑02 Result, предложение) | RCTF‑запрос: роль ревьюера артефактов AI; формат confirmed_risks/open_questions | Просмотр `prompts.md` P1‑02 Result | Добавление рисков без evidence |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | `prompts.md` (P1‑02 Result, предложение) | Проверка спорных утверждений JSON и перевод в «Вопросы» | Сопоставили с `TRAINING_PR.diff`, `context.md` | Жесткие выводы без источников |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | `prompts.md` (P1‑02 Result, предложение) | Альтернативы обращения со спорными пунктами JSON | Сравнение по критериям | Удаление без фиксации вопросов |
| RAG | [`rag/experiment.md`](rag/experiment.md) | `prompts.md` (P1‑02 Result, предложение) | Подтверждение рисков JSON только по разрешенным источникам | Проверка по `TRAINING_PR.diff`, `context.md` | Выводы вне источников |
| ReAct | [`react/experiment.md`](react/experiment.md) | `prompts.md` (P1‑02 Result, предложение) | Пошаговый аудит JSON, добавление evidence/checks, вынос вопросов | Сопоставление шагов и наблюдений | Изменение кода приложения — запрещено |

## Независимое ревью

| Замечание другой команды | Где исправили | Evidence |
|---|---|---|
| Двусмысленность | prompts.md — в JSON перенесли спорные пункты в «Открытые вопросы» | Ссылка: prompts.md, P1‑02 Result |
| Непроверяемое требование | prompts.md — добавили checks к подтверждённым рискам | Ссылка: prompts.md, P1‑02 Result |
| Пропущенный риск или источник | prompts.md — добавили evidence (file/line/fragment) | Ссылка: prompts.md, P1‑02 Result |
