# Собственный MCP: `olympiad-pricing`, tool `quote`

## Что это и зачем

- Код: [`mcp/olympiad_pricing/server.py`](../../mcp/olympiad_pricing/server.py) — stdio MCP-сервер (JSON-RPC 2.0) на стандартной библиотеке Python, подключён в [`.mcp.json`](../../.mcp.json).
- Tool `quote(program, months, grade?)` возвращает каноническую цену из `docs/requirements.md`: цену за месяц после скидки, скидку в % и ₽, итог и строки `display` ровно в том виде, как их показывает калькулятор на странице.
- Зачем: цены, скидки и соответствие класса программе — единственная нетривиальная логика проекта. Без tool агент считал бы их в уме или копировал из кода, который сам же проверяет. Tool берёт данные прямо из требований, поэтому годится как независимый эталон для калькулятора B; `AGENTS.md` велит спрашивать цены у него.
- Ошибочный вход (неизвестная программа, срок не 1/3/6, класс вне 5–9, класс не подходит программе) возвращается как `isError: true` с подсказкой, что исправить. Неизвестное имя tool — ошибка протокола JSON-RPC `-32602`.

## Реальный вызов из Claude Code (неинтерактивная сессия, claude-opus-5-5)

Сессия открыта в `practices/practice_04`, сервер подключён из `.mcp.json` проекта: `playwright`: connected, `olympiad-pricing`: connected. Разрешены только `quote`, Read, Grep.

Поручение: вызвать `quote` три раза (верный вход и два ошибочных), затем сверить формат `display` с `script.js`.

| # | Аргументы | Результат |
|---|---|---|
| 1 | `{"program": "start", "months": 6, "grade": 5}` | **успех**: `{"program":"start","program_name":"Старт","grades":[5,6],"months":6,"base_monthly_rub":4900,"discount_percent":10,"monthly_rub":4410,"discount_rub":2940,"total_rub":26460,"display":{"monthly":"4410 ₽","discount":"−10% (−2940 ₽)","total":"26 460 ₽"}}` |
| 2 | `{"program": "intensive", "months": 1, "grade": 6}` | **isError**: `Grade 6 does not match «Интенсив» (grades 9–9). For grade 6 the right program is «Старт».` |
| 3 | `{"program": "start", "months": 2}` | **isError**: `months must be one of [1, 3, 6], got 2.` |

Ответ агента (дословно):

> Формат `display` из вызова 1 совпадает с тем, что показывает страница. Вызовы 2 и 3 вернули ошибки, и это правильные отказы на неверный ввод. Файлы не менял.
>
> ## Ответы `quote`
>
> **1) `program=start, months=6, grade=5`: успех**
> ```json
> {"program":"start","program_name":"Старт","grades":[5,6],"months":6,
>  "base_monthly_rub":4900,"discount_percent":10,"monthly_rub":4410,
>  "discount_rub":2940,"total_rub":26460,
>  "display":{"monthly":"4410 ₽","discount":"−10% (−2940 ₽)","total":"26 460 ₽"}}
> ```
>
> **2) `program=intensive, months=1, grade=6`: ошибка**
> > Grade 6 does not match «Интенсив» (grades 9–9). For grade 6 the right program is «Старт».
>
> Это верно: «Интенсив» только для 9 класса. Мелкий косметический недочёт: класс из одного значения выводится как «9–9».
>
> **3) `program=start, months=2`: ошибка**
> > months must be one of [1, 3, 6], got 2.
>
> Это тоже верно: длительности в 2 месяца нет.
>
> ## Сверка с `script.js`
>
> `formatRub` (`script.js:27-31`) оставляет 4-значные числа без разделителя, а числа от 10 000 делит на группы по три цифры. Между группами и перед `₽` стоит неразрывный пробел (U+00A0). Строка скидки (`script.js:67-69`) собирается как `` `${sign}${percent}% (${sign}${formatRub(discount)})` ``, где знак `−` — это символ U+2212, а не дефис.
>
> Что посчитает страница для «Старт» × 6 месяцев (цена `data-price="4900"` в `index.html:273`, `DISCOUNTS[6] = 10` в `script.js:8`):
>
> | Поле | Страница | `display` из tool | Совпадает |
> |---|---|---|---|
> | В месяц | `4410 ₽` | `4410 ₽` | да |
> | Скидка | `−10% (−2940 ₽)` | `−10% (−2940 ₽)` | да |
> | Итого | `26 460 ₽` | `26 460 ₽` | да |
>
> Совпадают и сами символы. Через поиск по файлам проверил, что функция `rub()` в `mcp/olympiad_pricing/server.py:41-44` тоже ставит неразрывные пробелы в тех же местах, а знак `−` (U+2212) стоит в обоих файлах. Невидимой разницы между обычным и неразрывным пробелом там нет.
>
> Это вывод по чтению кода. В браузере вживую не проверял.

Итог сессии: `is_error: False`, шагов: 13. Bash не был в списке разрешённых: одну команду только на чтение (`sed`/`grep`) Claude Code пропустил сам, вторая (`python3 -c …`) отклонена (`permission_denials`). Файлы не менялись (`git status` чистый).

### Что изменилось после вызова

Агент заметил косметический недочёт: для «Интенсив» ошибка писала «grades 9–9». Исправлено в commit `0476661` (теперь «grade 9»), тест обновлён.

## Самопроверка по протоколу (`scripts/test_mcp_pricing.py`, часть `check.sh`)

Ожидаемые числа записаны в тесте вручную по требованиям, а не вычисляются кодом сервера. Тест запускает сервер и говорит с ним по stdio.

```
PASS  initialize returns serverInfo
PASS  tools/list exposes exactly one tool: quote
PASS  quote start × 1: 4900/мес, −0% (−0), итого 4900
PASS  quote start × 3: 4655/мес, −5% (−735), итого 13965
PASS  quote start × 6: 4410/мес, −10% (−2940), итого 26460
PASS  quote base × 1: 5900/мес, −0% (−0), итого 5900
PASS  quote base × 3: 5605/мес, −5% (−885), итого 16815
PASS  quote base × 6: 5310/мес, −10% (−3540), итого 31860
PASS  quote intensive × 1: 6900/мес, −0% (−0), итого 6900
PASS  quote intensive × 3: 6555/мес, −5% (−1035), итого 19665
PASS  quote intensive × 6: 6210/мес, −10% (−4140), итого 37260
PASS  requirements example (Старт, 6 мес., 5 класс) has the page's display strings
PASS  error input {"program": "olymp", "months": 1}
PASS  error input {"program": "start", "months": 2}
PASS  error input {"program": "start", "months": "6"}
PASS  error input {"program": "start", "months": 1, "grade": 4}
PASS  error input {"program": "intensive", "months": 1, "grade": 6}
PASS  error input {"program": "base", "months": 3, "grade": 9}
PASS  unknown tool name is a JSON-RPC error

19/19 MCP checks passed
```

Тест реально ловит ошибку: на копии требований, где скидка за 6 месяцев 20% вместо 10%, `check.sh` падает (`15/19 MCP checks passed`, `RESULT: FAIL`, exit 1).
