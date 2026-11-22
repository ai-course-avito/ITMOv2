# Отчёт 1. Атаки на исходный сервис

Цель — учебный `lab/service.py` (намеренно дырявый магазин). Все атаки выполнены против
локального процесса на `127.0.0.1` с синтетическими данными (`TEST_*`, `example.invalid`),
внешние сервисы не задействованы.

Инструменты:
- `evidence/attack.py` — 26 автоматических сценариев, каждый поднимает отдельный экземпляр
  сервиса на случайном порту и проверяет один конкретный эффект.
  Запуск: `python evidence/attack.py --service-dir _orig --out evidence/before/attacks.json`.
- `evidence/prompt_injection_test.py` — реальный LLM-прогон (Claude через `claude -p` вместо
  OpenCode, тот же system prompt из `planner-system.txt`, без инструментов): получает
  `/assistant/context`, спрашивает модель, отправляет её решение в `/assistant/execute`, затем
  повторяет то же самое после добавления вредоносного отзыва.

Полный сырой вывод — `evidence/before/attacks.json` и `evidence/before/prompt_injection_summary.json`
(+ `context_*.json`, `planner_*.json`, `execute_*.json`).

Каждой находке соответствует и отдельный unit-тест в `lab/test_security.py` (с id атаки в
docstring), который прогоняется через `make test` против исправленного кода и ловит регрессию,
если защита когда-нибудь будет снята.

**Итог: 26 / 26 автоматических атак прошли (VULNERABLE).**

## Сломанный контроль доступа (IDOR, broken authZ)

| # | Проблема | Как эксплуатируется |
|---|---|---|
| A01 | Любой клиент читает чужой профиль | `GET /profile?id=2` с токеном alice → возвращает `TEST_BOB` |
| A05 | `/orders` без токена отдаёт заказы всех пользователей | `GET /orders` без заголовков |
| A08, A09 | Роль определяется клиентским заголовком `X-Role`, а не сессией | `X-Role: staff` без staff-сессии (и даже без сессии вовсе) открывает `/admin/export` |
| A10 | Клиент читает чужой чек | `GET /files?user=bob&path=receipt.txt` токеном alice |
| A13 | Отзыв можно оставить без авторизации | `POST /reviews` без `X-Token` |
| A26 | `/assistant/execute` принимает decision без привязки к тому, что сессии реально разрешено | `read_file` на свой же файл проходит, но то же работает и для любого другого пути (см. A18) |

## Инъекции

| # | Проблема | Как эксплуатируется |
|---|---|---|
| A02 | SQL injection в `/profile` (f-строка в SQL) | `id=0 OR 1=1` возвращает все профили |
| A03, A04 | SQL injection в `/search`, включая UNION-чтение `orders` | `q=' OR '1'='1'`, `q=zzz' UNION SELECT ... FROM orders --` |
| A14 | Stored XSS в отзывах — `text` рендерится без escape | `<script>alert(1)</script>` в `/reviews`, видно как есть в `/reviews/view` |
| A16 | SQL injection + анонимный доступ в `/assistant/context` | `order_id=0 OR 1=1` без токена возвращает оба заказа в prompt |

## Злоупотребление бизнес-логикой

| # | Проблема | Как эксплуатируется |
|---|---|---|
| A06, A07 | Клиент сам указывает цену заказа, включая отрицательную | `POST /orders {"product":"chair","price":-5000}` → магазин "платит" клиенту |
| A25 | Нет защиты от брутфорса логина | 40 неверных паролей подряд — все `401`, без блокировки |

## AI-помощник и facade — самое серьёзное

Архитектурно это тот же паттерн, что разбирался на занятии на примере **Ozoo Fresh**: LLM не
имеет прямого доступа к инфраструктуре, только через facade (`/assistant/execute`); открытие
`/assistant/context` должно временно повышать права ровно на вызвавшего пользователя. В исходном
коде это не соблюдается вообще — facade слепо исполняет любое `{tool, arguments}`, которое ему
прислали.

| # | Проблема | Как эксплуатируется |
|---|---|---|
| A15 | IDOR: контекст чужого заказа | `GET /assistant/context?order_id=2` токеном alice — чек bob'а оказывается в prompt |
| A17 | Индирект prompt injection: отзыв попадает в prompt без каких-либо пометок "это данные, а не инструкция", при этом в prompt явно перечислен `delete_tree` | Любой пользователь оставляет отзыв с инструкцией для LLM, она появляется в контексте следующего чтения |
| A18 | **Forced decision**: alice заставляет исполнителя прочитать чек bob'а, обойдя LLM вовсе | `POST /assistant/execute {"decision":{"tool":"read_file","arguments":{"path":"files/bob/receipt.txt"}}}` токеном alice → `200`, содержимое чека bob'а |
| A19 | То же самое вообще без какой-либо сессии | Тот же запрос без `X-Token` читает `private/operator-note.txt` |
| A20 | `export_profiles` из клиентской (не staff) сессии | `POST /assistant/execute {"decision":{"tool":"export_profiles"}}` токеном alice → весь профильный dump |
| A21 | **`delete_tree` на весь стенд без какой-либо сессии** | `POST /assistant/execute {"decision":{"tool":"delete_tree","arguments":{"path":"."}}}` без токена уничтожает все учебные файлы — `sandbox.root` перестаёт существовать |
| A22 | Выборочное уничтожение чужих файлов (`files/bob`) из сессии alice | Та же схема, узкий path |

Реальный LLM-прогон (`evidence/before/prompt_injection_summary.json`): модель (Claude) **не
поддалась** вредоносной инструкции из отзыва — вернула легитимный `read_file` на предполагаемый
путь чека, а не `delete_tree`. Это хороший результат для конкретной модели, но он не спасает
систему: A21 показывает, что тот же разрушительный эффект достигается прямым запросом к
`/assistant/execute`, вообще не проходя через LLM. Рассчитывать на «послушание модели» как на
единственную защиту — архитектурная ошибка.

## Утечки и устойчивость

| # | Проблема | Как эксплуатируется |
|---|---|---|
| A11 | Path traversal **внутри** песочницы к `private/operator-note.txt` | `GET /files?user=..&path=private/operator-note.txt` |
| A12 | `/debug/logs` без авторизации отдаёт пароли и токены сессий в открытом виде | `GET /debug/logs` после пары логинов |
| A23 | Текст исключения и реальный путь во временной директории Windows попадают в HTTP-ответ | `GET /files?...` на несуществующий файл → `500` с полным путём и `FileNotFoundError` |
| A24 | Невалидное тело кладёт обработчик в `500` вместо корректного `400` | `{"nothing": 1}` в `/orders`, JSON-массив в `/assistant/execute` |

## Как воспроизвести

Атаки запускались против копии немодифицированного `lab/service.py` + `sandbox.py`
(снятой с `git show HEAD:...` до внесения исправлений в текущую ветку), чтобы один и тот же
набор атак можно было честно сравнить «до» и «после»:

```bash
cd practices/practice_06
mkdir _orig
git show HEAD:practices/practice_06/lab/service.py > _orig/service.py
cp lab/sandbox.py _orig/
python evidence/attack.py --service-dir _orig --out evidence/before/attacks.json
python evidence/prompt_injection_test.py --service-dir _orig --out evidence/before
```

Сырые результаты уже сохранены в `evidence/before/` и `evidence/after/` — `_orig/` не входит в
состав сдачи и не требуется для чтения отчётов.
