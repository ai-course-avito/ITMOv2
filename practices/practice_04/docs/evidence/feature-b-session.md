# Подтверждения: сессия Feature B

Выдержки из журнала Claude Code новой сессии в worktree `~/ITMOv2-p4-b/practices/practice_04`
(session `4aad1a27`, 2026-10-05, время UTC). Полный журнал не прикладывается: только шаги, относящиеся к критериям оценки.

## 1. Поручение (пользователь)

```
Реализуй фичу B по docs/requirements.md (включая раздел Clarifications).
Прочитай AGENTS.md и docs/style-guide.md. Используй skill ui-check.
Сохрани сценарии A: sh scripts/check.sh должен проходить.
Добавь в runner проверки для B, не ослабляя существующие.
Проверь B в браузере через Playwright MCP на порту 8001: мышью и клавиатурой.
Покажи diff и фактически выполненные команды. Не делай commit без моей приёмки.
```

## 2. AGENTS.md загружен в контекст сессии

- [18:20:22] instructions: `/Users/nokukagin/ITMOv2-p4-b/practices/practice_04/AGENTS.md` (type: Project, 3510 символов)

Сразу после этого агент читает `docs/requirements.md` и `docs/style-guide.md`:

```
[18:20:27] Bash: cat docs/requirements.md docs/style-guide.md; ls -la; ls scripts .claude; cat .claude/settings.json .mcp.json
```

## 3. Skill `ui-check` загружен

```
[18:20:25] Skill: {"skill": "ui-check", "args": "Implement feature B per docs/requirements.md (incl. Clarifications); keep A checks passing; add runner checks for B; verify in browser via Playwright on port 8001 with mouse and keyboard; show diff and commands; no commit."}
→ Launching skill: ui-check
```

## 4. Hook: результат проверки после каждой правки возвращается агенту

Сначала агент добавил проверки B в runner (они падают, пока B нет), затем реализовал B. Каждое событие ниже — реальный `PostToolUse` hook из `.claude/settings.json`.

**[18:21:29] FAIL после Edit `scripts/check_page.py`** — агенту вернулось:
```
scripts/check.sh FAILED after Edit on scripts/check_page.py:
== page contract (/Users/nokukagin/ITMOv2-p4-b/practices/practice_04)

== whitespace (git diff --check)
PASS  no whitespace errors in changes

RESULT: FAIL

Fix the cause; do not weaken the runner (docs/style-guide.md, rule 4).
```
Реакция агента: _That's expected: `check_signup` doesn't exist yet. Adding it now._

> Замечание: раздел «page contract» здесь пустой. Runner упал с ошибкой Python (функция ещё не существовала), а hook передаёт агенту только stdout runner, поэтому traceback до агента не дошёл. Агент правильно угадал причину, но это недостаток hook: нужно передавать и stderr.

**[18:21:46] FAIL после Edit `scripts/check_page.py`** — агенту вернулось:
```
scripts/check.sh FAILED after Edit on scripts/check_page.py:
FAIL  #signup has one <form>
Fix the cause; do not weaken the runner (docs/style-guide.md, rule 4).
```
Реакция агента: _Red as expected: `#signup` has no form yet. Next, the markup: the `#signup` section plus the «Выбрать» links on the cards._

**[18:22:05] FAIL после Edit `index.html`** — агенту вернулось:
```
scripts/check.sh FAILED after Edit on index.html:
FAIL  index.html loads script.js
FAIL  script.js sends no network requests
Fix the cause; do not weaken the runner (docs/style-guide.md, rule 4).
```
Реакция агента: _I'll make the consent label gender-neutral, then write `script.js`._

**[18:22:06] FAIL после Edit `index.html`** — агенту вернулось:
```
scripts/check.sh FAILED after Edit on index.html:
FAIL  script.js sends no network requests
FAIL  script.js exists
Fix the cause; do not weaken the runner (docs/style-guide.md, rule 4).
```
(Две правки `index.html` шли подряд, поэтому агент ответил на оба FAIL одним действием: написал `script.js`. После этого hook дал PASS.)

- [18:22:33] PASS → в контекст агента: `scripts/check.sh PASS after Write on script.js (62/62 checks passed)`
- [18:22:46] PASS → в контекст агента: `scripts/check.sh PASS after Edit on styles.css (62/62 checks passed)`
- [18:22:48] PASS → в контекст агента: `scripts/check.sh PASS after Edit on styles.css (62/62 checks passed)`
- [18:23:19] PASS → в контекст агента: `scripts/check.sh PASS after Edit on script.js (62/62 checks passed)`

Локальный журнал hook: [`check-hook-feature-b.txt`](check-hook-feature-b.txt).

## 5. Playwright MCP: проверка B в браузере

```
[18:23:07] browser_click — «Выбрать» on Старт card
```
```
[18:23:10] browser_evaluate
код: async () => { await new Promise(r => setTimeout(r, 1200)); const t = id => document.getElementById(id).textContent.replace(/ /g,' '); const s = document.getElementById('signup').getBoundingClientRect(); return { program: document.getElementById('signup-program').value, focused: document.activeElemen
…(обрезано)
→ ### Result
{
  "program": "start",
  "focused": "",
  "signupTop": 16,
  "monthly": "4900 ₽",
  "discount": "0% (0 ₽)",
  "total": "4900 ₽",
  "hintHidden": true
}
```
> Браузерная проверка нашла дефект: после «Выбрать» фокус не попадал в форму (`"focused": ""`). Агент исправил `script.js` (hook: PASS в 18:23:19), и повторная проверка ниже показывает `"focused": "signup-program"`.
```
[18:23:21] browser_click — «Выбрать» on Основа card
```
```
[18:23:22] browser_evaluate
код: async () => { await new Promise(r => setTimeout(r, 1200)); return { program: document.getElementById('signup-program').value, focused: document.activeElement.id, signupTop: Math.round(document.getElementById('signup').getBoundingClientRect().top), scrollY: Math.round(scrollY) }; }
→ ### Result
{
  "program": "base",
  "focused": "signup-program",
  "signupTop": 16,
  "scrollY": 3594
}
```
```
[18:23:28] browser_select_option — program select
```
```
[18:23:29] browser_click — 6 months radio label
```
```
[18:23:29] browser_evaluate
код: () => ['signup-monthly','signup-discount','signup-total'].map(id => document.getElementById(id).textContent.replace(/ /g,' '))
→ ### Result
[
  "4410 ₽",
  "−10% (−2940 ₽)",
  "26 460 ₽"
]
```
```
[18:23:35] browser_evaluate
код: () => { const f = document.getElementById('signup-form'); const out = {}; for (const p of ['start','base','intensive']) for (const d of ['1','3','6']) { f.elements.program.value = p; f.elements.program.dispatchEvent(new Event('change',{bubbles:true})); const r = f.querySelector(`input[name=duration]
…(обрезано)
→ ### Result
{
  "startx1": "4900 ₽ | 0% (0 ₽) | 4900 ₽",
  "startx3": "4655 ₽ | −5% (−735 ₽) | 13 965 ₽",
  "startx6": "4410 ₽ | −10% (−2940 ₽) | 26 460 ₽",
  "basex1": "5900 ₽ | 0% (0 ₽) | 5900 ₽",
  "basex3": "5605 ₽ | −5% (−885 ₽) | 16 815 ₽",
  "basex6": "5310 ₽ | −10% (−3540 ₽) | 31 860 ₽",
  "intensivex1": "6900 ₽ | 0% (0 ₽) | 6900 ₽",
  "intensivex3": "6555 ₽ | −5% (−1035 ₽) | 19 665 ₽",
  "intensivex6": "6210 ₽ | −10% (−4140 ₽) | 37 260 ₽",
  "reset": "— | — | — / hint visible: true"
}
```
```
[18:23:38] browser_click — «Отправить заявку» button
```
```
[18:23:55] browser_run_code_unsafe
код: async (page) => {
  await page.goto('http://localhost:8001/?fresh=1');
  const order = [];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return 'BODY'
…(обрезано)
→ ### Result
["a \"Перейти к содержанию\" outline=solid","a \"Olympiad Start, в начало страницы\" outline=solid","a \"Для кого\" outline=solid","a \"Программы\" outline=solid","a \"Как проходят занятия\" outline=solid","a \"Тренеры\" outline=solid","a \"Вопросы\" outline=solid","a \"Записаться\" outline=solid","a \"Выбрать программу\" outline=solid","a \"Как проходят занятия\" outline=solid","a \"Выбрать «Старт»\" outline=solid","a \"Выбрать «Основа»\" outline=solid","a \"Выбрать «Интенсив»\" outline=solid","summary \"Нужен ли опыт олимпиад?\" outline=solid","summary \"Как выбрать программу?\" outline=solid","summary \"Зачем нужен входной тест?\" outline=solid","summary \"Сколько стоит пробное занятие?\" outline=solid","a \"Записаться\" outline=solid","select#signup-program \"Программа\" outline=solid","select#signup-grade \"Класс ребёнка\" outline=solid","input#signup-duration-1 \"1 месяц
…(обрезано)
```
```
[18:24:09] browser_run_code_unsafe
код: async (page) => {
  const log = {};
  const requests = [];
  page.on('request', r => requests.push(r.method() + ' ' + r.url()));
  await page.goto('http://localhost:8001/?fresh=2');
  requests.length = 0;
  const active = () => page.evaluate(() => { const el = document.activeElement; return el.id ||
…(обрезано)
→ ### Result
{"onPick":"Выбрать «Старт»","afterEnter":{"focus":"signup-program","program":"start","monthly":"4900 ₽"},"grade":"","duration6":{"checked":"6","total":"26 460 ₽"},"consent":true,"onSubmit":"signup-duration-6","errors1":[{"field":"signup-grade","describedby":"Выберите класс ребёнка."},{"field":"signup-email","describedby":"Проверьте email: например, name@example.ru."}],"focusAfterInvalid":"signup-grade","onFix":"","afterFix":{"focus":"signup-grade","program":"start","monthly":"4410 ₽","discount":"−10% (−2940 ₽)","total":"26 460 ₽","programError":""},"summary":null,"requestsAfterLoad":[]}
```
```
[18:24:27] browser_run_code_unsafe
код: async (page) => {
  const log = {};
  const requests = [];
  page.on('request', r => requests.push(r.method() + ' ' + r.url()));
  await page.goto('http://localhost:8001/?fresh=3');
  requests.length = 0;
  const active = () => page.evaluate(() => { const el = document.activeElement; return el.id ||
…(обрезано)
→ ### Result
{"onPick":"Выбрать «Старт»","afterEnter":{"focus":"signup-program","program":"start","monthly":"4900 ₽","hash":"#signup"},"onGrade":"signup-grade","grade":"7","onDuration":"signup-duration-1","duration":{"checked":"6","monthly":"4410 ₽","discount":"−10% (−2940 ₽)","total":"26 460 ₽"},"onName":"signup-name","onEmail":"signup-email","onConsent":"signup-consent","consent":true,"onSubmit":"button.button button--primary signup-form__submit","errors":["signup-program: Для 7 класса подходит «Основа». Выбрать «Основу»","signup-email: Проверьте email: например, name@example.ru."],"focusAfterInvalid":"signup-program","onFix":"Выбрать «Основу»","afterFix":{"focus":"signup-program","program":"base","monthly":"5310 ₽","discount":"−10% (−3540 ₽)","total":"31 860 ₽","programError":"","invalid":["signup-email"]},"onEmail2":"signup-email","summary":{"text":"Спасибо, заявка готова!\nПрограмма\n
…(обрезано)
```
```
[18:24:38] browser_run_code_unsafe
код: async (page) => {
  const out = {};
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('http://localhost:8001/?fresh=4');
  await page.click('a[data-program="intensive"]');
  await page.selectOption('#signup-grade', '5');
  await page.click('.signup-form__submit');
  out.m
…(обрезано)
→ ### Result
{"mismatch":"Для 5 класса подходит «Старт». Выбрать «Старт»","afterMouseFix":{"program":"start","total":"4900 ₽"},"w360":{"scrollWidth":360,"clientWidth":360},"w768":{"scrollWidth":768,"clientWidth":768},"w1280":{"scrollWidth":1280,"clientWidth":1280}}
```
```
[18:24:38] browser_console_messages — warning
→ ### Result
Total messages: 0 (Errors: 0, Warnings: 0)
```
```
[18:24:45] browser_run_code_unsafe
код: async (page) => {
  const dir = '/private/tmp/claude-501/-Users-nokukagin-ITMOv2-p4-b-practices-practice-04/4aad1a27-6083-4990-aa3b-c0a36ae89653/scratchpad/';
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('http://localhost:8001/?shot=1');
  await page.click('a[data-pr
…(обрезано)
→ ### Result
"ok"
```

Скриншоты агента: [`signup-1280.png`](signup-1280.png), [`signup-360.png`](signup-360.png), [`card-360.png`](card-360.png).

## 6. Приёмка и commit (решение пользователя)

- [18:26:44] пользователь: «which branch are we currently in?»
- [18:26:56] пользователь: «you can commit new changes»

```
[18:26:59] M  index.html
A  script.js
M  scripts/check_page.py
M  styles.css
96775a3 Add sign-up form with live price calculation (feature B)
fbfb81c Clarify feature B requirements
```
