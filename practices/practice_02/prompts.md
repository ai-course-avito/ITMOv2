# Журнал экспериментов Практики 2

- Выбранный слабый артефакт Практики 1: project_management.md
- Что в нём нужно улучшить: Заменить шаблонные блоки на конкретику, добавить явные риски, актуализировать зависимые работы и владельца. Обновить диаграмму Гантта - она некорректна
- Как поймём, что изменение полезно: Отсутствие плейсхолдеров, все даты/ответствености/задачи конкретизированы. Связка с метриками. Консистентность ссылок и терминов.

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) |  |  |  |  |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | [`rctf/project_management.md`](rctf/project_management.md) (копия `project_management.md`) | Добавлена колонка «Риски и меры» с evidence `file:line` из P1-02; «Проверка» заменена на DoD со ссылками на `tests_*` и метрики problem.md (≥95%, 100%, ≥99%); Гант исправлен: явные id, зависимости `after`, удалён шаблонный текст; заполнены «Для чего» и тип промпта | `file:line` сверены с P1-02 и TRAINING_PR.diff; пороги 20k/10s — из CASE.md; метрики — из problem.md; ссылки на файлы practice_01 существуют | Владельцы и календарные обязательства (нет данных о людях); заявление о фактическом прохождении тестов; OBS-1 как инкремент (отклонён в P1-02 без evidence) |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) |  |  |  |  |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) |  |  |  |  |
| RAG | [`rag/experiment.md`](rag/experiment.md) |  |  |  |  |
| ReAct | [`react/experiment.md`](react/experiment.md) |  |  |  |  |
