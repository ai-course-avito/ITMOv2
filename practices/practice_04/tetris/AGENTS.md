# Тетрис — правила проекта для агента

Браузерный тетрис с собственным дизайном. Чистый JS (ES-модули), без зависимостей и сборки.

## Где что

- Контракт с фичами A и B и способами проверки: `docs/requirements.md`.
- Style guide: `docs/style-guide.md` — **прочитай перед любым изменением кода**.
- Логика: `src/game.js` (чистые функции). Рекорд в `localStorage`: `src/record.js` (хранилище передаётся параметром). Интерфейс: `index.html`, `src/ui.js`, `src/styles.css`.
- Пример теста: `tests/smoke.test.js`.

## Проверка

- Единственная команда проверки: `sh scripts/check.sh` (`node --test` по `tests/*.test.js`).
- После каждой правки файла хук `.claude/hooks/check-after-edit.sh` запускает её сам и возвращает `[check-after-edit] … PASS` или `FAIL` с хвостом лога. При FAIL исправляй причину в коде, а не тест.
- Внешний вид проверяй в браузере: MCP встроенного браузера (`mcp__Claude_Browser__preview_start` с `name: "tetris"` — поднимает `python3 -m http.server` на 5173), затем скриншот и `read_console_messages` — в консоли не должно быть ошибок.

## Skills

- `.claude/skills/test-driven-development/` — для логики в `src/game.js`: сначала падающий тест, потом код. Прочитай `SKILL.md` и `writing-good-tests.md`.
- `.claude/skills/frontend-design/` — для интерфейса: сначала план (палитра, шрифты, раскладка, принципы), проверка плана против шаблонных решений, потом код, потом самокритика по скриншоту.

## Нельзя без явного поручения

- Менять `docs/requirements.md`, `scripts/check.sh`, `.claude/` и `AGENTS.md`.
- Удалять или ослаблять тесты.
- Подключать зависимости, CDN-скрипты и фреймворки (веб-шрифты Google Fonts — можно).
- Делать `git commit`, `git push`, `git merge`.
