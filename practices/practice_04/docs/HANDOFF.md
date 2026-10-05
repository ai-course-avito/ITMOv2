# Handoff: practice 4, Olympiad Start

Для новой сессии агента или человека. Прочитай вместе с `AGENTS.md`.

## Состояние (2026-10-05)
- Ветка `2026_Nokulagin_practice_4` = `main` + commits практики 4. Не отправлена (push не делался).
- **Feature A** (одностраничный лендинг) готова: `index.html`, `styles.css`.
- **Feature B** (форма записи и калькулятор цены) готова: `#signup` в `index.html`, `script.js`.
  Сделана в отдельном worktree `practice-04-b`, прошла review через Explore-субагента, обе находки исправлены
  (`c344a03`), затем `git merge --ff-only` в эту ветку.
- **Собственный MCP** `olympiad-pricing` (tool `quote`) готов: `mcp/olympiad_pricing/server.py`.
- Worktree `~/ITMOv2-p4-b` больше не нужен: ветка `practice-04-b` полностью вошла в эту ветку.

## Источники правды
- Требования: `docs/requirements.md` (Feature A, Feature B, раздел Clarifications с решениями владельца).
- Правила: `AGENTS.md`, короткий список легко нарушаемых правил: `docs/style-guide.md`.
- Цены: tool `quote` читает их из `docs/requirements.md`; на странице цены в `data-price` и `DISCOUNTS` в `script.js`.

## Проверки
- `sh scripts/check.sh` — контракт страницы A и B (62 проверки), самопроверка MCP по stdio (19), `git diff --check`,
  синтаксис `script.js`. Ожидается `RESULT: PASS`.
- Hook `PostToolUse` (`.claude/settings.json`) запускает runner после каждой правки и возвращает FAIL/PASS агенту.
- Браузер: Playwright MCP из `.mcp.json`. Страницу сначала поднять: `python3 -m http.server 8000`.

## Ограничения и известные ловушки
- В браузере Playwright `script.js` может прийти из HTTP-кэша: после правок обходить кэш (`page.route('**/*', r => r.continue())`)
  и проверять `deliveryType` в `performance.getEntriesByType('resource')`.
- `scroll-behavior: smooth`: после клика по якорю ждать окончания прокрутки или эмулировать `prefers-reduced-motion: reduce`.
- Worktree не изолирует порты: во втором worktree брать другой порт (8001, 8002…).
- Runner статический: клавиатуру, фокус, контраст и консоль проверять только в браузере.
- Не проверено: реальные скринридеры, браузеры кроме Chromium.

## Что осталось (решения владельца, не агента)
- Своими словами: почему исправлять находки review (`docs/evidence/review-b.md` §6), обоснование подключений,
  разбор skill `ui-check`, `reflection.md`.
- Push ветки и сдача; отчёт для сдачи: `docs/report.html`, доказательства: `docs/evidence/`.

## Проверка этого handoff
Новая сессия: «Прочитай AGENTS.md и docs/HANDOFF.md. Что уже сделано и что осталось? Запусти проверку проекта.
Пока ничего не меняй.» — пересказ должен совпасть с разделами выше, а `sh scripts/check.sh` дать `RESULT: PASS`.
