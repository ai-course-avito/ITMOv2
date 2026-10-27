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

Следующие шаги **ещё не выполнены**: согласование, `speckit-plan`,
`speckit-tasks`, реализация и `speckit-converge`.
Установленные файлы навыков сами по себе не доказывают выполнение этих шагов.

## Сравнение по наблюдаемым артефактам

| Вопрос | OpenSpec 1.14.1 из занятия | Spec Kit 1.2.3 в этом ДЗ |
|---|---|---|
| Единица работы | Change: proposal, specs, design, tasks | Feature directory: spec, затем plan и tasks |
| Постоянные правила | `openspec/config.yaml`, context и rules | `.specify/memory/constitution.md` и шаблоны |
| Как появляется содержание | Агент читает CLI instructions и пишет документы | Агент выполняет skills, использующие установленные шаблоны и scripts |
| Проверка | `status`, `validate`, тесты проекта и приёмка | Checklist спецификации, анализ согласованности, тесты и converge |
| Завершение | Sync принятых specs и archive change | Реализация задач и converge относительно артефактов |
| Наше применение | Известный процесс занятия; код CLI не является LLM | Две команды используют один набор принципов и раздельные specs |

Ни один инструмент не заменяет согласование UI с логикой: координатор должен
сопоставить данные, ошибки и состояния, а пользователь — принять решения.
Для ДЗ сохраняем drafts отдельно от будущих согласованных версий; разницу
нельзя получить из одного только признака наличия файлов.

## Источники

- [Официальный quickstart Spec Kit](https://github.github.com/spec-kit/quickstart.html)
- [Официальная установка](https://github.github.com/spec-kit/installation.html)
- [Команды и выбор feature directory](https://github.github.com/spec-kit/reference/core.html)
- Локальные шаблоны и skills, установленные CLI 1.2.3 в `project/`.
- OpenSpec: `openspec --version` → 1.14.1; схема из `openspec schemas --json`;
  маршрут в учебной презентации, страницы 2–15.

Сравнение опыта работы и личные выводы студентки будут добавлены после
согласования и выполнения фичи; сейчас они не выдумываются.
