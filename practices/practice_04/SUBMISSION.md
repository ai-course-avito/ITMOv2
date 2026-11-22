# Практика 4. Среда агента, skill и собственный MCP

Проект — [`review-api/`](review-api/): FastAPI-сервис AI-помощника ревьюера PR из `TRAINING_PR.diff` Практики 1. Это продолжение сквозного проекта, поэтому правила SEC-1, API-1, REL-1, OUT-1 и QA-1 взяты из Context Pack первой практики и перенесены в контракт [`docs/requirements.md`](review-api/docs/requirements.md).

Агент — OpenCode 1.18.31 с моделью `opencode/big-pickle`. Каждый прогон — отдельная сессия `opencode run`, сырые события и читаемые протоколы лежат в [`evidence/`](evidence/). Скрипт запуска — [`tools/run_agent.py`](tools/run_agent.py).

> Презентация практики рассчитана на OpenCode 2.0.20, у меня установлен 1.18.31. Отличия, которые пришлось учесть: MCP описывается как `"mcp": {"имя": {...}}` без обёртки `servers`; хук — плагин с событием `tool.execute.after`, а не `ctx.tool.hook("execute.after")`; skills лежат в `.opencode/skills/`, их список показывает `opencode debug skill`.

## Что лежит в среде

| Компонент | Файл | Зачем |
|---|---|---|
| Правила проекта | [`review-api/AGENTS.md`](review-api/AGENTS.md) | Где контракт и style guide, единственная команда проверки, что нельзя менять без поручения. Без него агент не знает, что «проверить» — это `sh scripts/check.sh`, а не `pytest` из случайного каталога |
| Контракт | [`review-api/docs/requirements.md`](review-api/docs/requirements.md) | Правила и фичи A/B с проверяемыми кодами ответа: агент пишет тесты по ним, а не по догадке |
| Style guide | [`review-api/docs/style-guide.md`](review-api/docs/style-guide.md) | Пять правил: тесты через HTTP, ID правила в имени теста, ошибки через `HTTPException`, без новых зависимостей, не ослаблять runner |
| Runner | [`review-api/scripts/check.sh`](review-api/scripts/check.sh) | Одна доверенная команда: pytest по `tests/` (API и логика MCP-инструмента) |
| Hook | [`review-api/.opencode/plugins/check-after-edit.js`](review-api/.opencode/plugins/check-after-edit.js) | После каждого `edit`/`write` запускает runner и дописывает `PASS`/`FAIL` с хвостом лога к результату инструмента — агент видит падение в том же шаге, без отдельной команды |
| Skill | [`review-api/.opencode/skills/pr-diff-review/`](review-api/.opencode/skills/pr-diff-review/) | Процедура ревью diff по правилам проекта + валидатор, который проверяет, что каждая цитата действительно стоит в diff на указанной строке |
| Собственный MCP | [`review-api/mcp_server/`](review-api/mcp_server/), подключение в [`review-api/opencode.json`](review-api/opencode.json) | Инструмент `scan_diff`: детерминированная предпроверка diff по API-1 и SEC-1 до того, как diff увидит LLM |
| Права | [`review-api/opencode.json`](review-api/opencode.json) | `bash` запрещён целиком, кроме runner, валидатора skill и `git status`/`git diff`; `webfetch` запрещён |

**Почему именно эти подключения.** Главная проблема, которую я видел в ДЗ 1–3, — правдоподобные ответы без оснований: в ДЗ 1 ответ P1-02 выглядел образцовым, а в ДЗ 3 локальная модель выдумала GitHub Actions. Поэтому все подключения в этой среде — про проверку. Хук возвращает факт прогона тестов, валидатор skill отклоняет цитату, которой нет на указанной строке, MCP-инструмент считает лимит и ищет секреты кодом, а не «на глаз». Сторонние MCP (Context7, GitHub) этой задаче ничего не дают: зависимостей мало, работа с GitHub в сервис намеренно не входит (SCOPE-1).

## 1. Среда применяется в работе

| Что показываем | Подтверждение |
|---|---|
| Агент читает `AGENTS.md` и находит контракт, команду проверки, запреты и пример теста; называет требования фичи A со ссылкой `docs/requirements.md:22-27`; ничего не меняет | [`evidence/01_agents_md.md`](evidence/01_agents_md.md) |
| Фича A по TDD: агент читает style guide → добавляет 5 тестов → хук возвращает **FAIL** (`4 failed, 7 passed`) → агент правит `app/api.py` → хук возвращает **PASS** (`11 passed`). В конце агент называет применённое правило style guide и место в коде | [`evidence/02_feature_a.md`](evidence/02_feature_a.md), шаги 9–10; журнал хука [`evidence/06_hook_log.txt`](evidence/06_hook_log.txt); коммит `feat(review-api): фича A` |
| Права работают: `ls` агенту запрещён, он переключается на `glob` | [`evidence/03_skill_review.md`](evidence/03_skill_review.md), шаг 7 |

Код фичи A я прочитал и принял: валидация до вызова LLM, коды 422/413 и тело `{"detail": "diff too large"}` — по контракту, у каждого теста есть проверка `len(llm.calls) == 0`, граница «ровно 20 000» покрыта.

## 2. Skill `pr-diff-review`

**Устройство.** [`SKILL.md`](review-api/.opencode/skills/pr-diff-review/SKILL.md) — пять шагов: предпроверка MCP-инструментом → чтение контракта → кандидаты в риски с подтверждением строкой diff (QA-1) → JSON не больше чем с тремя рисками по образцу [`references/out1-example.json`](review-api/.opencode/skills/pr-diff-review/references/out1-example.json) → [`scripts/validate_review.py`](review-api/.opencode/skills/pr-diff-review/scripts/validate_review.py) до кода выхода 0. Валидатор проверяет структуру OUT-1, а затем по hunk-заголовкам восстанавливает номера строк нового файла и проверяет, что `evidence` дословно стоит в `file:line`. Остановка: если MCP вернул `blocked`, ревью не пишется, а секреты не цитируются.

**Запуск и проверенный результат.** Запрос — одна фраза: «Отревьюй samples/training_pr.diff по процедуре проекта». Агент сам загрузил skill, вызвал `review-tools_scan_diff`, прочитал контракт и diff, записал [`reviews/training_pr.json`](review-api/reviews/training_pr.json) и прогнал валидатор: `OK … 3 риск(а) подтверждены строками diff` — [`evidence/03_skill_review.md`](evidence/03_skill_review.md). Я сверил три риска с diff вручную: `app/api.py:10` (API-1), `app/review_service.py:14` (SEC-1), `app/review_service.py:15` (REL-1) — строки и цитаты верные, четвёртый кандидат (OUT-1) агент честно отбросил из-за лимита в три риска.

**Чем валидатор полезен на чужих данных.** На ответе P1-02 из Практики 1 он отклоняет один из трёх рисков: трёхстрочная цитата привязана к `app/api.py:9`, а там только `def create_review(...)`:

```text
FAIL: risks[2].evidence: не найдено в app/api.py:9 (там: 'def create_review(payload: dict) -> dict[str, str]:')
```

## 3. Собственный MCP `review-tools`

**Инструмент.** `scan_diff(diff_path)` в [`mcp_server/review_tools_server.py`](review-api/mcp_server/review_tools_server.py) на Python SDK `mcp` 2.3 (`MCPServer`, stdio). Логика вынесена в [`mcp_server/diff_scan.py`](review-api/mcp_server/diff_scan.py) и покрыта тестами [`tests/test_diff_scan.py`](review-api/tests/test_diff_scan.py). Возвращает размер и лимит API-1, список файлов, найденные секреты с `файл:строка` и замаскированным фрагментом, итог `ok`/`blocked`. Ошибочный вход — путь вне проекта, несуществующий файл, не unified diff, не UTF-8 — возвращается как ошибка инструмента (`isError`), а не как правдоподобный результат.

**Реальные вызовы.**

| Сценарий | Через агента OpenCode | Через MCP-клиент SDK |
|---|---|---|
| Корректный diff → `ok` | [`03_skill_review.md`](evidence/03_skill_review.md), шаг 2 | [`05_mcp_smoke_client.txt`](evidence/05_mcp_smoke_client.txt) |
| Diff с токеном → `blocked`, `app/settings.py:3`, секрет замаскирован | [`04b_mcp_errors.md`](evidence/04b_mcp_errors.md), шаг 1 | там же |
| Не diff → ошибка | [`04b_mcp_errors.md`](evidence/04b_mcp_errors.md), шаг 2 | там же |
| Путь вне проекта → ошибка | [`04b_mcp_errors.md`](evidence/04b_mcp_errors.md), шаг 3 | там же (`../../../etc/passwd`) |
| Несуществующий файл → ошибка | — | там же |

`opencode mcp list` показывает `✓ review-tools connected`. Клиент [`mcp_server/smoke_client.py`](review-api/mcp_server/smoke_client.py) запускает сервер той же командой, что и OpenCode, и повторяет все пять сценариев.

**Где пришлось вмешаться.** В первой попытке ([`04a_mcp_no_call.md`](evidence/04a_mcp_no_call.md)) агент не вызвал инструмент ни разу и выдумал ответы: для `../../README.md` написал «invalid diff format», хотя сервер отвечает «path must stay inside the project root». Повтор с требованием «реально вызови и перескажи дословно» дал три настоящих вызова. Вывод: наличие подключённого MCP не означает, что агент им воспользовался, — проверять нужно по событиям вызова.

## 4. Проект «Тетрис»: две фичи со скачанными skills

Отдельный небольшой проект [`tetris/`](tetris/) по маршруту практики. Исполнитель — субагенты Claude Code; среда — та же, что требует практика.

| Компонент | Файл | Зачем |
|---|---|---|
| Правила | [`tetris/AGENTS.md`](tetris/AGENTS.md) (+ `CLAUDE.md` → `@AGENTS.md`) | Контракт, команда проверки, skills, MCP, запреты |
| Скачанные skills | [`tetris/.claude/skills/`](tetris/.claude/skills/) | `frontend-design` (anthropics/skills@41bbe19, Apache-2.0) — дизайн без шаблонов; `test-driven-development` (obra/superpowers@b9e75dd, MIT) — логика через падающий тест |
| Hook | [`tetris/.claude/hooks/check-after-edit.sh`](tetris/.claude/hooks/check-after-edit.sh), конфиг [`tetris/.claude/settings.json`](tetris/.claude/settings.json) | PostToolUse после Edit/Write: запускает `sh scripts/check.sh`, PASS возвращает агенту как контекст, FAIL — как ошибку; работает и в worktree |
| MCP | встроенный браузер `mcp__Claude_Browser__*`, конфиг [`tetris/.claude/launch.json`](tetris/.claude/launch.json) | Скриншот и консоль: дизайн по skill нельзя принять без взгляда на результат |
| Runner | [`tetris/scripts/check.sh`](tetris/scripts/check.sh) | `node --test`, без зависимостей |

| Этап практики | Что было | Подтверждение |
|---|---|---|
| Среда | Коммит среды до работы агента | `f4a831d` |
| Фича A | Субагент: 38 тестов по TDD, хук 12×FAIL → 21×PASS, дизайн «тетрадь в клетку» по плану, по скриншотам найдено и исправлено 5 дефектов | [`A-subagent-report.md`](evidence/tetris/A-subagent-report.md), [`A-hook-log.txt`](evidence/tetris/A-hook-log.txt), [`A-start-screen.jpg`](evidence/tetris/A-start-screen.jpg), [`A-gameplay.jpg`](evidence/tetris/A-gameplay.jpg); коммит `fcdf6e7` |
| Фича B в worktree | Новый субагент в `git worktree` (ветка `practice-04-b`): призрак, hold, рекорд; 24 теста; найден баг hold по Shift | [`B-subagent-report.md`](evidence/tetris/B-subagent-report.md), [`B-hook-log.txt`](evidence/tetris/B-hook-log.txt) |
| Review субагентом | Отдельный read-only субагент: 3 замечания; мои решения — 2 исправить, 1 принять и закрепить в правилах | [`B-review.md`](evidence/tetris/B-review.md); коммит `5cd7ad3` |
| Объединение | `git merge --ff-only practice-04-b`, общая проверка: 65 тестов Тетриса + 11 review-api | — |
| Handoff | `docs/HANDOFF.md`, новая сессия восстановила состояние и сама прогнала проверку | [`C-handoff.md`](evidence/tetris/C-handoff.md) |

Запуск: `cd practices/practice_04/tetris && python3 -m http.server 5173` → `http://localhost:5173/`.

## 5. Рефлексия

[`reflection.md`](reflection.md).

## Как повторить

```bash
cd practices/practice_04/review-api
make install                         # .venv: fastapi, httpx, pytest, mcp
make check                           # 11 тестов
opencode mcp list                    # review-tools connected
opencode debug skill | grep pr-diff  # skill найден
.venv/bin/python mcp_server/smoke_client.py
cd .. && python3 tools/run_agent.py --name demo "Отревьюй samples/with_secret.diff по процедуре проекта."
```

Фичу B (timeout LLM, REL-1) в этой сдаче не делал: домашнее задание её не требует, контракт для неё в `docs/requirements.md` уже есть.
