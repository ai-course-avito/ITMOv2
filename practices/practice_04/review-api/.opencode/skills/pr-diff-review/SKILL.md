---
name: pr-diff-review
description: Review a pull-request diff of this project against its rules (SEC-1, API-1, QA-1, OUT-1) and save a validated OUT-1 JSON review with file:line evidence. Use when asked to review a diff file or a PR.
license: MIT
compatibility: opencode
metadata:
  project: review-api
  validator: scripts/validate_review.py
---

# PR diff review

Процедура ревью одного diff по правилам проекта. Результат — JSON в формате OUT-1, прошедший валидатор.

## Вход

- `diff_path` — путь к unified diff внутри проекта, например `samples/training_pr.diff`.

## Процедура

1. **Предпроверка.** Вызови MCP-инструмент `review-tools_scan_diff` с `diff_path`.
   Если `verdict` = `blocked` — остановись: верни `reasons` и номера строк из `secrets`.
   Секреты не цитируй, diff дальше не анализируй (SEC-1, API-1).
2. **Правила.** Прочитай `docs/requirements.md`. Других правил не придумывай.
3. **Кандидаты.** Прочитай diff. Для каждого кандидата в риск найди подтверждение:
   строку из diff (файл + номер строки *нового* файла, считается от заголовка `@@ -a,b +c,d @@`)
   или ID правила. Кандидат без подтверждения отбрасывается (QA-1).
4. **Ответ.** Оставь не больше трёх рисков. Сохрани JSON в `reviews/<имя-diff>.json`
   по образцу `references/out1-example.json`. `evidence` — дословный фрагмент строки diff без ведущего `+`.
5. **Проверка.** Запусти
   `.venv/bin/python .opencode/skills/pr-diff-review/scripts/validate_review.py reviews/<имя-diff>.json --diff <diff_path>`.
   Пока код выхода не 0 — исправляй JSON по сообщениям валидатора. Валидатор не ослабляй.

## Границы

- Не меняй код приложения, тесты и `docs/` (SCOPE-1: сервис и ревьюер только советуют).
- Не делай approve, merge и git commit.
- Если данных недостаточно — напиши это в `summary`, а не додумывай.

## Что вернуть пользователю

- путь к JSON и последнюю строку вывода валидатора;
- список рисков в виде `файл:строка — риск (правило)`;
- что не проверено.
