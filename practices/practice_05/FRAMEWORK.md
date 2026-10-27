# GitHub Spec Kit и сравнение с OpenSpec

Для ДЗ 5 выбран **GitHub Spec Kit**. Это другой SDD-фреймворк относительно
OpenSpec из практического занятия. Установлен настоящий `specify-cli==1.2.3`
из PyPI; источником команды установки служит официальная документация проекта.

## Реальное применение

1. CLI установлен в `/tmp/itmo-spec-kit-venv` через Python venv и pip.
2. Выполнен `specify version`, версия 1.2.3.
3. Из `practices/practice_05` выполнена команда:

```bash
/tmp/itmo-spec-kit-venv/bin/specify init project \
  --integration codex --integration-options=--skills --script sh --non-interactive
```

[Исходный вывод](evidence/spec-kit-init.txt) подтверждает установку шаблонов,
скриптов, workflow и Codex skills. Git extension не устанавливалось; работа
остаётся в выделенной пользователем ветке `practice_05`.

4. В `project` запущен штатный template resolver для constitution и specification:

```bash
.specify/scripts/bash/resolve-template.sh constitution-template --json
.specify/scripts/bash/resolve-template.sh spec-template --json
```

Выводы сохранены в `evidence/*-template-resolution.json`.
Навык `speckit-constitution` использован для общих правил; `speckit-specify` —
для независимых спецификаций UI и логики. Для двух команд выбраны разные
feature directories. Активный feature для дальнейших CLI-команд задаётся
явно через `SPECIFY_FEATURE_DIRECTORY`, поэтому он не зависит от имени git-ветки.

5. Пользователь согласовал контракт; две команды обновили свои спецификации.
Побайтные снимки «после» и сравнение с «до» сохранены в evidence, затем сделан
commit 5301bc5 без прикладного кода.
6. Для обеих feature directories реально запущены setup-plan.sh и setup-tasks.sh,
написаны research/data-model/contracts/quickstart/plan/tasks. Скрипты prerequisites
нашли все обязательные артефакты. У UI 10 задач, у логики 14.
7. Выполнен `speckit-implement`: закрыты 10 задач UI и 14 задач логики,
интеграционные проверки сохранены в evidence/final-check.txt (после аудита — 53 теста).
8. Обе команды применили `speckit-converge` после реализации и проверок.
Сверены требования, планы, задачи и constitution; новых задач не потребовалось.
Результаты: [UI](evidence/ui-convergence.md), [логика](evidence/logic-convergence.md).

## Сравнение по наблюдаемым артефактам

| Вопрос | OpenSpec 1.14.1 из занятия | Spec Kit 1.2.3 в этом ДЗ |
|---|---|---|
| Единица работы | Change: proposal, specs, design, tasks | Feature directory: spec, затем plan и tasks |
| Постоянные правила | `openspec/config.yaml`, context и rules | `.specify/memory/constitution.md` и шаблоны |
| Как появляется содержание | Агент читает CLI instructions и пишет документы | Агент выполняет skills, использующие установленные шаблоны и scripts |
| Проверка | `status`, `validate`, тесты проекта и приёмка | Checklist спецификации, анализ согласованности, тесты и converge |
| Завершение | Sync принятых specs и archive change | Реализация задач и converge относительно артефактов |
| Наше применение | Известный процесс занятия; код CLI не является LLM | Две команды используют один набор принципов и раздельные specs |

Фреймворк задаёт порядок работы; данные, ошибки и состояния UI и логики
сопоставляются в общем контракте, который принимается человеком.
Для ДЗ сохранили drafts отдельно от согласованных версий; разницу
нельзя получить из одного только признака наличия файлов.

## Источники

- [Официальный quickstart Spec Kit](https://github.github.com/spec-kit/quickstart.html)
- [Официальная установка](https://github.github.com/spec-kit/installation.html)
- [Команды и выбор feature directory](https://github.github.com/spec-kit/reference/core.html)
- Локальные шаблоны и skills, установленные CLI 1.2.3 в `project/`.
- OpenSpec: `openspec --version` → 1.14.1; схема из `openspec schemas --json`;
  маршрут в учебной презентации, страницы 2–15.

Наблюдение по процессу: раздельные feature directories позволили вести планы
команд независимо, но формат ошибок и evidence всё равно потребовал общего
контракта. Converge опирался на исполняемые проверки и чтение кода; сам набор
шаблонов не выявил три пограничные ошибки parser/redaction, найденные ревью.
Личные выводы студентки записаны в [REFLECTION.md](REFLECTION.md).
