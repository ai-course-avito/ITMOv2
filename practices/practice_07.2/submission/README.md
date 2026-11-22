# ИТМО 7.2 · Поддержка и статистика

Экспорты n8n — [классификатор](classifier.json), [обработка Issues](triage.json), [недельный отчёт](weekly-report.json).

Классификатор принимает `title` и `body`, вызывает Qwen в Ollama и возвращает `type` и `confidence` через Structured Output Parser. Основной workflow вызывает его через Execute Workflow. Switch выбирает одну ветку. При `confidence < 0.8` или неизвестном типе он добавляет `needs-triage`. Сценарий не публикует комментарии.

## Классификация

[Список Issues с метками](evidence/issue-labels.jpg)

| Тестовый Issue | Метка | Выполнение |
| --- | --- | --- |
| [№2](https://github.com/vlklk/itmo-n8n-lab/issues/2) | `bug` | [№8](evidence/execution-bug.jpg) |
| [№3](https://github.com/vlklk/itmo-n8n-lab/issues/3) | `task` | [№10](evidence/execution-task.jpg) |
| [№4](https://github.com/vlklk/itmo-n8n-lab/issues/4) | `feature` | [№12](evidence/execution-feature.jpg) |
| [№5](https://github.com/vlklk/itmo-n8n-lab/issues/5) | `needs-triage` | [№15](evidence/execution-needs-triage.jpg) |

Для просмотра Issues ревьюверу понадобится доступ к тестовому репозиторию.

## Недельный отчёт

Расписание — понедельник в 09:00 по Москве. Четыре запроса отдельно собирают Issues, созданные и закрытые за период, и PR, созданные и влитые за период. Code node группирует записи по категории и автору. При неполном ответе GitHub или превышении 100 записей в категории workflow завершится ошибкой, чтобы не отправлять неполную сводку.

[Ручной запуск №21](evidence/gmail-execution.jpg) собрал 4 новых Issues и 1 новый PR, сформировал HTML и успешно отправил отчёт через Gmail. [Полученное письмо](evidence/gmail-received.jpg) подтверждает доставку и отображение таблицы. В локальном n8n подключён Gmail OAuth с правом `gmail.send`. Расписание сохранено в workflow, для проверки использован ручной запуск.

В экспорте оставлен адрес `SET_RECIPIENT@example.invalid`. При переносе укажите своего получателя. Сравнение с прошлой неделей и AI-аннотация относятся к бонусной части.

При импорте в другой экземпляр выберите Sub-workflow в узле «Вызвать классификатор» и настройте GitHub, Ollama и Gmail. Метки `bug`, `task`, `feature` и `needs-triage` должны существовать в тестовом репозитории.
