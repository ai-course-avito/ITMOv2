# Review Feature B через subagent

## 1. Поручение пользователя (18:32:20 UTC)

```
Запусти Explore agent: проверь diff последнего commit (git show HEAD) по docs/requirements.md,
назови подтверждённые проблемы с доказательствами. Файлы не меняй.
```

## 2. Вызов subagent (18:32:34 UTC)

- инструмент `Agent`, `subagent_type: Explore`, описание: «Review last commit vs requirements»
- метаданные: `agentType: Explore`, фоновый запуск
- вызовы инструментов subagent: {'Bash': 6}; правок файлов: 0 (только чтение)

<details><summary>Поручение, которое основной агент передал subagent</summary>

```
Read-only review. Do NOT modify any files. Working directory: /Users/nokukagin/ITMOv2-p4-b/practices/practice_04 (a git worktree; run commands from here).

Task: review the diff of the last commit (`git show HEAD`) against `docs/requirements.md` (Feature B section AND its "Clarifications" list, plus "Shared requirements" and the Feature A constraint "Feature A must keep working: all sections, counts, anchors and CTAs unchanged"). Also consult `AGENTS.md` and `docs/style-guide.md` for project rules (BEM, colors only from :root tokens, no invented real-world claims, Russian visible text, semantic HTML, headings in order, 2-space indent, accessibility).

Files in the commit: index.html, styles.css, script.js (new), scripts/check_page.py (runner; new checks for B were explicitly requested by the user — verify they did not weaken or alter existing checks).

Report ONLY confirmed problems, each with concrete evidence: file:line, quoted code, and the exact requirement text it violates (quote it). For each, explain the concrete failing scenario (inputs → wrong observable result). If you reason about runtime JS behaviour, trace the code precisely; you may run `node` with a small standalone snippet to verify pure logic (e.g. number formatting / price math) — do not write files into the project (use /private/tmp/claude-501/ only if needed, or node -e). You may run `sh scripts/check.sh` (it is read-only).

Specifically verify:
1. Price math for all 3 programs × durations 1/3/6 and the Clarification example (Старт, 6 months → 4410 ₽ / month, discount −10% (−2940 ₽), total 26 460 ₽). Check the formatRub implementation — note: check whether the source literally contains the escape ' ' or a raw char, using `grep -n "u00a0" script.js` and `od -c` on the relevant lines.
2. «—» + «Выберите программу» before program chosen; duration default 1.
3. Validation: all fields required, consent, email format, grade/program mismatch message format «Для 7 класса подходит «Основа»» + button «Выбрать «Основу»» which switches and recalculates.
4. Errors next to field, Russian, announced via aria-live or aria-describedby.
5. Valid submit: no network, form replaced by summary with program, duration, total, «Мы свяжемся с вами по email»; focus moves to summary heading.
6. «Выбрать» buttons on cards scroll to #signup and preselect program; edge cases (e.g. after summary shown).
7. Only one #signup; Feature A counts/anchors/CTAs unchanged.
8. Runner: existing checks untouched; any new check that is wrong, vacuous, or would pass on broken pages (e.g. truthiness bugs such as `expect(program and ...)` returning a list).
9. Edge cases in the re-validation-on-change logic (e.g. the change handler calls validate() on ALL fields when one invalid field changes — does that show errors on fields the user hasn't touched? Only matters if it can occur before a submit) and in the mismatch flow (e.g. stale fix button, error not cleared when grade changes so it now matches).

Separate the output into: "Confirmed problems" (with evidence, severity high/medium/low) and "Checked and OK" (one line each). Do not list speculative issues as confirmed; put uncertain ones under "Unconfirmed / needs browser". Keep the final report concise.
```
</details>

## 3. Итоговый отчёт subagent (дословно)

I found one real bug and one weak runner check. Everything else in HEAD (96775a3) matches the requirements. `sh scripts/check.sh` gives RESULT: PASS, 62/62.

### Confirmed problems

**1. A grade/program mismatch error stays on screen after the user fixes the grade (medium)**
- Where: `script.js:162-166`
  ```js
  form.addEventListener('change', function (event) {
    if (event.target === program || event.target.name === 'duration') updatePrice();
    if (event.target.getAttribute('aria-invalid') === 'true') validate();
  });
  ```
- Why it happens: when the grade doesn't match, `showMismatch` (line 94) puts the error and `aria-invalid` on the **program** select. The grade select passed its own "required" check, so `clearError(grade)` leaves it without `aria-invalid`. Later changes to the grade therefore never re-run `validate()`.
- How to reproduce:
  1. Program = Основа, grade = 5, fill the other fields, submit. The error «Для 5 класса подходит «Старт».» appears with a «Выбрать «Старт»» button.
  2. Change the grade to 7, which now matches Основа. The error and button stay, and the program select keeps `aria-invalid="true"`.
  3. Change the grade to 9 instead: the screen still says «Для 5 класса подходит «Старт»», which is now wrong. The right advice would be «Интенсив».
  4. Clicking that leftover «Выбрать «Старт»» switches to Старт, which conflicts with the grade now selected. Nothing re-checks the grade until the next submit.
- Requirements it breaks: "grade must match the program … otherwise suggest the right program", and the clarification "the error names the right program and has a button that switches to it". The suggestion shown is out of date, and screen readers still treat the program field as invalid.
- Submitting again does recalculate everything correctly, so no wrong data gets through. The problem is only what the user sees and hears.

**2. A new runner check, «no program is preselected by default», can pass when a program is preselected (low)**
- Where: `scripts/check_page.py`, in the new `check_signup`:
  ```python
  expect(program and "selected" in next((o.attrs for o in program[0].find_all("option") if o.attrs.get("value") == ""), {}), ...)
  ```
- What's wrong: it only checks that the empty option has `selected`. If someone also adds `selected` to `<option value="start">`, the browser shows Старт as chosen, yet the check still passes.
- Requirement: "Before a program is chosen, price, discount and total show «—» with the hint «Выберите программу»".
- This is a weak test, not a bug in the page. The `program and …` / `controls and …` / `js and …` truthiness patterns you asked me to look at are safe, because `expect()` wraps its argument in `bool()`.

### Checked and OK
- **Prices:** I ran `formatRub` from the source in node for all 3 programs × 1/3/6 months. Every value is a whole number, with no rounding drift.
  - Старт, 6 months: 4410 ₽ / month, −10% (−2940 ₽), total 26 460 ₽. This matches the clarification example exactly.
  - Other results: 4655/735/13 965; 5605/885/16 815; 5310/3540/31 860; 6555/1035/19 665; 6210/4140/37 260.
- **formatRub source:** there is no ` ` escape. Lines 28-29 contain the raw no-break space byte (`c2 a0`) and a raw ₽ (`e2 82 bd`). Output is correct; the only downside is that the character is invisible when reading the code.
- **Discount with 1 month:** shows «0% (0 ₽)». That is acceptable.
- **Before a program is chosen:** price, discount and total show «—», the hint «Выберите программу» is visible, and its `hidden` toggle isn't overridden by CSS. Duration defaults to 1 month.
- **Validation:** every field is required, including consent, and the email format is checked. Messages are in Russian and placed next to each field. Error elements are linked with `aria-describedby` and fields get `aria-invalid`. Focus goes to the first invalid field, and a mismatch error comes first.
- **Mismatch message:** reads «Для 7 класса подходит «Основа».» with the button «Выбрать «Основу»». The button switches the program, recalculates the price, clears the error and moves focus to the select.
- **Old fix buttons:** they don't pile up across submits, because `validate()` clears the program error before `showMismatch` adds a new one.
- **Re-checking on change:** `aria-invalid` is only set by a submit, so errors can't appear on fields the user hasn't touched before the first submit.
- **Valid submit:** `preventDefault` stops it, the form has no `action`, and there are no `fetch`/XHR calls. The form is replaced by a summary with the program, duration, total and «Мы свяжемся с вами по email». Focus moves to the summary `h3` (`tabindex="-1"`), which sits under the section's `h2`.
- **«Выбрать» buttons on cards:** each links to `#signup` with its own `data-program`, preselects that program, clears its error, updates the price and moves focus to the select. After the summary is shown, `isConnected` guards against errors and the link just scrolls.
- **Feature A:** there is still exactly one `#signup`, and the placeholder was replaced, not duplicated. The only Feature A change is the three «Выбрать» links that Feature B asks for. The runner's counts, anchors and CTAs all pass.
- **Runner:** the diff only adds lines. No existing check was removed or changed, and `check.sh` was not touched.
- **CSS:** new rules use BEM names and only `var(--…)` tokens, with no raw hex. Indentation is 2 spaces and `git diff --check` is clean.
- **Language and content:** visible text is Russian, and there are no invented real-world claims.

### Unconfirmed / needs browser
- Whether the fragment scroll and the `setTimeout` focus on the program select behave as expected with keyboard and screen reader.
- Whether a screen reader actually announces errors added after submit. They are linked by `aria-describedby` only, with no `aria-live`; the requirement allows either.
- Whether the `aria-live="polite"` region, which wraps the prices and the submit button, is too chatty.
- Visible focus style on the summary heading.
- Layout at 360px and 1280px.

Files reviewed: `/Users/nokukagin/ITMOv2-p4-b/practices/practice_04/script.js`, `/Users/nokukagin/ITMOv2-p4-b/practices/practice_04/index.html`, `/Users/nokukagin/ITMOv2-p4-b/practices/practice_04/styles.css`, `/Users/nokukagin/ITMOv2-p4-b/practices/practice_04/scripts/check_page.py`

## 4. Основной агент сверил находки с кодом

Агент нашёл одну реальную ошибку на странице и одну слабую новую проверку в runner. Остальное в коммите `96775a3` соответствует `docs/requirements.md`. Обе находки я сверил с кодом, они верные. Файлы не менялись.

### Подтверждённые проблемы

**1. Ошибка несовпадения класса и программы остаётся на экране после смены класса (средняя)**
- Где: `script.js:162-166`. Ошибку повторно проверяет только то поле, у которого стоит `aria-invalid`. При несовпадении `showMismatch` ставит ошибку и `aria-invalid` на поле **программы**, а с класса `clearError(grade)` её снимает. Поэтому смена класса проверку не запускает.
- Как воспроизвести:
  1. Выбрать «Основа», класс 5, отправить. Появляется «Для 5 класса подходит «Старт».» и кнопка «Выбрать «Старт»».
  2. Сменить класс на 7, который подходит «Основе». Ошибка и кнопка остаются, у программы по-прежнему `aria-invalid="true"`.
  3. Сменить класс на 9. На экране всё ещё совет про «Старт», хотя нужен «Интенсив». Кнопка переключит на неподходящую программу.
- Нарушает требование: «otherwise suggest the right program» и уточнение «the error names the right program…» — совет на экране устаревший.
- Неверные данные через это не проходят: повторная отправка всё проверяет заново. Страдает только то, что пользователь видит и слышит.
- Как исправить: при изменении класса или программы запускать `validate()`, если на программе уже показана ошибка.

**2. Проверка «no program is preselected by default» в runner слишком слабая (низкая)**
- Где: `scripts/check_page.py`, функция `check_signup`. Проверка смотрит только на `selected` у пустого варианта. Если добавить `selected` ещё и к `<option value="start">`, браузер покажет «Старт» выбранным, а проверка всё равно пройдёт.
- Как исправить: дополнительно требовать, чтобы ни у одного варианта с непустым `value` не было `selected`.

### Что агент проверил и подтвердил
- Цены для всех 9 сочетаний посчитаны верно, пример из Clarifications совпадает точно.
- Состояние «—» с подсказкой и срок 1 месяц по умолчанию.
- Валидация, сообщения на русском, связь ошибок через `aria-describedby`.
- После отправки: сводка без сетевого запроса, фокус на заголовке.
- Кнопки «Выбрать»: предвыбор программы и защита, когда форма уже заменена сводкой.
- `#signup` один, в фиче A ничего не сломано.
- Старые проверки runner не тронуты.
- Цвета только из токенов, видимый текст на русском, выдуманных фактов нет.
- В `formatRub` неразрывный пробел записан как реальный невидимый символ, а не как `\u00a0`. Вывод правильный, но символ трудно заметить при чтении кода.

### Что агент оставил как «нужен браузер»
Часть этого я уже проверил раньше в Playwright:
- Фокус на поле программы после «Выбрать» (с отложенным `setTimeout`) работает.
- Горизонтальной прокрутки нет на 360, 768 и 1280 px.

По-прежнему не проверено:
- как скринридер реально озвучивает ошибки и блок цены с `aria-live`;
- видимый стиль фокуса на заголовке сводки.

Исправить обе проблемы отдельным коммитом?

## 5. Независимое воспроизведение находки 1 (Playwright MCP, другая сессия)

| Шаг | Ошибка у поля «Программа» |
|---|---|
| «Основа» + 5 класс → отправить | `aria-invalid=true`, «Для 5 класса подходит «Старт». Выбрать «Старт»» |
| сменить класс на 7 (подходит «Основе») | та же ошибка остаётся |
| сменить класс на 9 (нужен «Интенсив») | та же ошибка про «Старт» |
| нажать кнопку «Выбрать «Старт»» | программа `start`, класс `9`: **кнопка ставит неподходящую программу** |

Последствие хуже, чем в отчёте: неверные данные не отправятся (повторная отправка проверяет всё заново), но кнопка-подсказка ведёт пользователя к неправильному выбору.

## 6. Решение пользователя и исправление

- [18:38:47 UTC] пользователь в сессии B: «да исправь» — исправлять обе находки.
- _TODO (своими словами): почему исправлять. Например: находка 1 ведёт пользователя к неверной программе
  (см. §5), находка 2 — дыра в runner, а style guide (правило 4) разрешает усиливать проверки._

Как агент исправлял (сессия B, 18:38–18:41 UTC):
1. Сначала воспроизвёл находку 1 в браузере (стало: ошибка про «Старт» остаётся при классе 7, 9, пустом).
2. Исправил `script.js`. Повторная проверка «ничего не изменилось»: браузер брал старый `script.js` из HTTP-кэша
   (`deliveryType: "cache"`). `Network.setCacheDisabled` не помог, помог `page.route` — после этого скрипт из сети.
3. На свежем скрипте первая версия правки оказалась недостаточной (кнопка-исправление не находилась после смены класса);
   агент доработал: после первой попытки отправки форма перепроверяется при каждом изменении и при выборе программы из карточки/кнопки.
4. Находка 2: сначала показал, что слабая проверка проходит на странице с `selected` у «Старт», затем усилил её — на той же копии FAIL, на реальной странице PASS.
5. Hook после каждой правки: PASS (62/62). Commit `c344a03` «Fix stale grade/program suggestion and tighten preselect check».

## 7. Независимая проверка исправления (другая сессия, Playwright MCP, кэш обойдён через `page.route`)

| Шаг | Результат |
|---|---|
| скрипт загружен | из сети (`network`) |
| класс 5 до отправки | ошибок нет (`aria-invalid`: 0) — валидация только после отправки |
| «Основа» + 5 → отправить | «Для 5 класса подходит «Старт». Выбрать «Старт»» |
| класс → 7 | ошибка снята |
| класс → 9 | «Для 9 класса подходит «Интенсив». Выбрать «Интенсив»» |
| нажать кнопку | программа `intensive`, класс 9, ошибки нет, цена 6900 ₽ |
