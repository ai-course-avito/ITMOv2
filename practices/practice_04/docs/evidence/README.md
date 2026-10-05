# Подтверждения для сдачи практики 4

Критерии из README практики → где лежит подтверждение. Наличие файла само по себе не подтверждение,
поэтому ссылки ведут на фактические вызовы и их результат.

| Критерий | Подтверждение |
|---|---|
| Применение `AGENTS.md` | [feature-b-session.md §2](feature-b-session.md#2-agentsmd-загружен-в-контекст-сессии): новая сессия загрузила `AGENTS.md` и сама прочитала требования и style guide; [§4](feature-b-session.md#4-hook-результат-проверки-после-каждой-правки-возвращается-агенту): агент ссылается на правило 4 style guide |
| Применение skill | [feature-b-session.md §3](feature-b-session.md#3-skill-ui-check-загружен) (вызов `Skill ui-check` моделью), [feature-a-and-setup.md §1–2](feature-a-and-setup.md) (вызовы `/ui-check`, шаг «сначала падающая проверка») |
| Применение MCP | [feature-b-session.md §5](feature-b-session.md#5-playwright-mcp-проверка-b-в-браузере) (21 вызов Playwright MCP), [feature-a-and-setup.md §3, §5](feature-a-and-setup.md) |
| Hook возвращает результат агенту | [feature-b-session.md §4](feature-b-session.md#4-hook-результат-проверки-после-каждой-правки-возвращается-агенту): 4 FAIL → 4 PASS в живой сессии; журналы [`check-hook-feature-b.log`](check-hook-feature-b.log), [`check-hook-manual-demo.log`](check-hook-manual-demo.log) |
| Обоснование подключений | _TODO: текст в отчёте_ |
| Skill: устройство и запуск | `../../.claude/skills/ui-check/SKILL.md` + запуски выше; _TODO: разбор в отчёте_ |
| Собственный MCP | _TODO_ |
| `reflection.md` | _TODO_ |
| Feature B проверена отдельно | [independent-check-b.md](independent-check-b.md), скриншоты [`signup-1280.png`](signup-1280.png), [`signup-360.png`](signup-360.png), [`card-360.png`](card-360.png) |
| Review B через subagent | [review-b.md](review-b.md): вызов Explore agent (только чтение), его отчёт, сверка основным агентом, воспроизведение в браузере, решение пользователя «да исправь», commit `c344a03` и его независимая проверка; _TODO: обоснование решения своими словами_ |

## Найдено и исправлено по ходу

- Hook передавал агенту только stdout runner: при падении `check_page.py` (первый FAIL в сессии B) агент видел пустой раздел без причины.
  Исправлено: hook добавляет stderr runner (traceback). Проверено на копии с `NameError` — traceback дошёл в сообщении hook.
