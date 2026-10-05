# Подтверждения: Feature A и настройка среды

Выдержки из журнала основной сессии Claude Code (session `d5a9e2c4`, время UTC). Только шаги, относящиеся к критериям.

## 1. Skills, вызванные пользователем

- [2026-10-02 07:54:14] `/ui-check` — «ничего не меняй, проверь нынешний проект»
- [2026-10-02 07:54:54] `/frontend-design` — «»
- [2026-10-02 07:55:40] `/frontend-design` — «Реализуй фичу A, после проверь с помощью playwright нажимая на каждую кнопку и другие вещи»
- [2026-10-02 07:55:40] `/ui-check` — «Реализуй фичу A, после проверь с помощью playwright нажимая на каждую кнопку и другие вещи»
- [2026-10-02 08:01:46] `/frontend-design` — «Реализуй фичу A, после проверь с помощью playwright нажимая на каждую кнопку и другие вещи»
- [2026-10-02 08:01:46] `/ui-check` — «Реализуй фичу A, после проверь с помощью playwright нажимая на каждую кнопку и другие вещи»

## 2. Feature A: сначала падающая проверка, потом реализация (процедура skill `ui-check`, шаг 3)

```
[2026-10-02 07:56:16] browser_evaluate (критерии приёмки A)
→ "FAIL: header+nav | main+footer | wordmark | header CTA Записаться | exactly 3 benefits | Для кого 5–9 | exactly 3 programs | program Старт | program Основа | program Интенсив | topics+format | 3 steps | 3 coaches, svg avatars, no imgs | 4 FAQ details | #signup CTA + target | hero CTAs"
```
```
[2026-10-02 07:58:32] browser_evaluate (критерии приёмки A)
→ "PASS"
```

## 3. Playwright MCP: каждая кнопка и FAQ мышью, затем клавиатура, ширины, контраст

```
[2026-10-02 08:02:12] browser_run_code_unsafe
→ {"linkResults":[{"i":0,"href":"#main","text":"Перейти к содержанию","note":"skip-link, tested via keyboard"},{"text":"Olympiad Start","href":"#hero","ok":true,"top":16},{"text":"Для кого","href":"#audience","ok":true,"top":16},{"text":"Программы","href":"#programs","ok":true,"top":16},{"text":"Как проходят занятия","href":"#how","ok":true,"top":16},{"text":"Тренеры","href":"#coaches","ok":true,"top":16},{"text":"Вопросы","href":"#faq","ok":true,"top":16},{"text":"Записаться","href":"#signup","ok":true,"top":457},{"text":"Выбрать программу","href":"#programs","ok":true,"top":16},{"text":"Как проходят занятия","href":"#how","ok":true,"top":16},{"text":"Записаться","href":"#signup","ok":true,"top":457}],"faq":[{"q":"Нужен ли опыт олимпиад?","opened":true,"closed":true},{"q":"Как выбрать программу?","opened":true,"closed":true},{"q":"Зачем нужен входной тест?","opened":true,"closed":true},{"q":"Сколько стоит пробное занятие?","opened":true,"closed":true}],"errors":["Failed to load resource: the server responded with a status of 404 (File not found)"]}
```
```
[2026-10-02 08:02:42] browser_run_code_unsafe
→ {"focusables":15,"tabbedUnique":13,"wrapAfterLast":["Перейти к содержанию Olympiad ","Перейти к содержанию"],"noOutline":[],"seq":["Перейти к содержанию","Olympiad Start","Для кого","Программы","Как проходят занятия","Тренеры","Вопросы","Записаться","Выбрать программу","Как проходят занятия","Нужен ли опыт олимпиад?","Как выбрать программу?","Зачем нужен входной тест?","Сколько стоит пробное занятие?","Записаться"],"skipVisible":true,"skipHash":"#main","kbOpen":true,"kbClosed":true,"kb":[{"sel":"#hero a[href=\"#programs\"]","hash":"#programs"},{"sel":"#hero a[href=\"#how\"]","hash":"#how"},{"sel":"#cta a[href=\"#signup\"]","hash":"#signup"},{"sel":"header a[href=\"#signup\"]","hash":"#signup"}],"errors":[]}
```
```
[2026-10-02 08:02:55] browser_run_code_unsafe
→ {"overflow":{"360":{"scrollW":360,"clientW":360,"hScroll":false,"wide":[]},"768":{"scrollW":768,"clientW":768,"hScroll":false,"wide":[]},"1280":{"scrollW":1280,"clientW":1280,"hScroll":false,"wide":[]}},"contrastFailures":[]}
```
```
[2026-10-02 08:03:15] browser_run_code_unsafe
→ {"out":{"360":{"hScroll":false,"headerH":194},"768":{"hScroll":false,"headerH":114},"1280":{"hScroll":false,"headerH":67}},"acceptance":"PASS","errors":[]}
```

## 4. Runner и hook до живой сессии (ручная проверка на реальном событии PostToolUse)

```
[2026-10-05 17:41:45] ### 1) temporary break: #coaches -> #trainers
1
scripts/check.sh FAILED after Edit on index.html:
FAIL  every #anchor has a target (missing: trainers)
Fix the cause; do not weaken the runner (docs/style-guide.md, rule 4).
hook exit: 2

### 2) fix back
(no index.html diff = restored)
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "scripts/check.sh PASS after Edit on index.html (34/34 checks passed)"}}
hook exit: 0

### 3) edit outside the project is ignored
hook exit: 0 (no output)

### log
2026-10-05T20:41:46	Edit	index.html	exit=1
2026-10-05T20:41:46	Edit	index.html	exit=0
```
Runner на испорченной копии:
```
################ broken copy
FAIL  every #anchor has a target (missing: trainers)
FAIL  exactly 4 FAQ <details>
31/33 checks passed
RESULT: FAIL
exit code: 0
exit code (direct): 1
```

## 5. Playwright MCP из `.mcp.json` проекта запускается (stdio, версия закреплена)

```
[2026-10-05 18:10:51] server: {'name': 'Playwright', 'version': '1.64.0-alpha-1790635538000'}
25 tools, e.g. ['browser_close', 'browser_resize', 'browser_console_messages', 'browser_handle_dialog', 'browser_emulate_media', 'browser_evaluate']
```
