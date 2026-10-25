# Журнал экспериментов Практики 2

Файл ведёт OpenCode по вашим запросам. Агент записывает фактические результаты экспериментов и вносит изменения в связанные файлы. Свою оценку сообщайте ему в чате; вручную заполнять шаблон не нужно.

- Выбранный слабый артефакт Практики 1: `practices/practice_01/product_management.md`
- Что в нём нужно улучшить: детализацию Gherkin-сценариев и Acceptance Criteria, покрытие краевых случаев
- Как поймём, что изменение полезно: сценарии учитывают таймауты геокодера, лимиты запросов и состояние Redis (промах, stale, недоступность)

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | [product_management.md — User stories и acceptance criteria](../practice_01/product_management.md#user-stories-и-acceptance-criteria) | Добавлены сценарии: таймаут геокодера, промах/прогрев кэша | Поиск ключевых фраз и diff | Отклонён слишком общий SLA без чисел |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | [product_management.md — User stories и acceptance criteria](../practice_01/product_management.md#user-stories-и-acceptance-criteria) | Добавлены сценарии: лимит 429 и negative cache на 60с | Поиск ключевых фраз и diff | Отклонены агрессивные ретраи |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | [product_management.md — User stories и acceptance criteria](../practice_01/product_management.md#user-stories-и-acceptance-criteria) | Уточнены условия таймаута (1500 мс) и сохранность локальных результатов | Проверка формулировок и консистентности | Отклонено «падать 5xx при деградации Redis» |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | [product_management.md — User stories и acceptance criteria](../practice_01/product_management.md#user-stories-и-acceptance-criteria) | Выбрана стратегия stale-while-revalidate для протухшего кэша | Проверка наличия сценария SWR | Отклонён «жёсткий инвалидационный кэш» |
| RAG | [`rag/experiment.md`](rag/experiment.md) | [product_management.md — User stories и acceptance criteria](../practice_01/product_management.md#user-stories-и-acceptance-criteria) | Синхронизация терминов с Context Pack (Redis TTL 600с) | Сопоставление с Context Pack | Отклонено TTL 24ч как неподтверждённое |
| ReAct | [`react/experiment.md`](react/experiment.md) | [product_management.md — User stories и acceptance criteria](../practice_01/product_management.md#user-stories-и-acceptance-criteria) | Добавлен сценарий degraded mode при недоступности Redis | Логи действий и поиск фраз | Отклонена схема circuit breaker в ТЗ |
