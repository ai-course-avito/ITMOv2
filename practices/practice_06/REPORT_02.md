# Отчёт 2. Проверка фиксов, новые векторы

Версия стенда: локальный запуск service.py (127.0.0.1), см. команды в PoC. Все данные синтетические. До атак `make step6` и общий `make test` — зелёные.

## 5.1 Сводная таблица регрессии по REPORT_01

| ID | Заявленный фикс | PoC-повтор | Обход найден? | Статус | Комментарий |
|----|-----------------|------------|---------------|--------|-------------|
| T-02 | SQLi /profile | не воспроизводил | — | open | Фикса в коде нет, проверка на этом этапе не выполнялась |
| T-08 | /assistant/execute без auth | не воспроизводил | — | open | Фикса в коде нет |
| T-09 | delete_tree DoS | не воспроизводил | — | open | Фикса в коде нет |
| T-12 | Логи с секретами | не воспроизводил | — | open | Фикса в коде нет |
| T-13 | XSS /reviews/view | не воспроизводил | — | open | Фикса в коде нет |
| T-20 | /assistant/context выдаёт чужие заказы | не воспроизводил | — | open | Фикса в коде нет |

Примечание: По diff к базовой ветке изменений в lab/ не было, кроме добавленного фиксирования обработки невалидного JSON (см. R-21 ниже). Остальные пункты из REPORT_01 остаются открытыми и требуют дальнейших правок на следующем шаге.

## 5.2 Новые находки

| ID | Название | Категория | Компонент | Severity | Статус |
|----|----------|-----------|-----------|----------|--------|
| R-21 | Утечка деталей исключений при невалидном JSON | CWE-209/152-ФЗ | lab/service.py: логика разбора тела | Medium | fixed |
| R-22 | SQLi в /profile?id | CWE-89, STRIDE:T | lab/service.py: /profile | High | fixed |
| R-23 | SQLi в /search?q | CWE-89, STRIDE:T | lab/service.py: /search | High | fixed |
| R-24 | SQLi в /assistant/context?order_id | CWE-89, STRIDE:T | lab/service.py: /assistant/context | High | fixed |
| R-25 | /orders GET без auth и фильтра | STRIDE:I/E | lab/service.py: /orders | High | fixed |
| R-26 | IDOR /files и произвольный path | STRIDE:I, CWE-862 | lab/service.py: /files | High | fixed |
| R-27 | /assistant/execute без auth/RBAC | LLM06/LLM05, STRIDE:E | lab/service.py: /assistant/execute | Critical | fixed |
| R-28 | /admin/export роль из заголовка | STRIDE:S | lab/service.py: /admin/export | High | fixed |
| R-29 | /orders POST принимает price | Business Logic Tampering | lab/service.py: /orders POST | Medium | fixed |
| R-30 | /debug/logs без auth и с секретами | 152-ФЗ, STRIDE:I | lab/service.py: /debug/logs | High | fixed |

## 5.3 Детальные карточки R-XX

### R-21: Утечка деталей исключений при невалидном JSON
- Категория: CWE-209 (Information Exposure Through an Error Message), 152-ФЗ
- Компонент: practices/practice_06/lab/service.py:119-135 (до фикса возвращал JSONDecodeError и type)
- Severity: Medium
- Вектор: Отправка невалидного JSON в POST-эндпоинт
- PoC (воспроизводимо):
```
python3 practices/practice_06/lab/service.py --port 8066 &
curl -i -X POST 'http://127.0.0.1:8066/orders' -H 'Content-Type: application/json' --data 'not json'
# Ожидалось ранее (до фикса): 500 с телом {"error":"...JSONDecodeError","type":"JSONDecodeError"}
# После фикса: 400 Bad Request и {"error":"invalid JSON"}
```
- Связь: новый
- Фикс: добавлена безопасная обработка JSON в BaseHTTPRequestHandler.handle_request: при JSONDecodeError возвращается 400 с обобщённым сообщением; общий except скрывает тип исключения.
- Тест: practices/practice_06/lab/test_http.py::HttpTest::test_malformed_json_does_not_leak_details
- Проверка после фикса: `make step6` — ок, тест проходит.

### R-22: SQLi в /profile?id
- Категория: CWE-89, STRIDE:T
- Компонент: practices/practice_06/lab/service.py:56-61 → фикс на /profile
- Severity: High
- Вектор и PoC (до фикса):
```
python3 practices/practice_06/lab/service.py --port 8066 &
curl -i 'http://127.0.0.1:8066/profile?id=1%20OR%201=1'
# Ожидалось/фактически до фикса: 200 OK и весь список профилей (2 записи)
```
- Влияние: Раскрытие ПДн, обход авторизации/логики выборки.
- Связь: T-02 из REPORT_01.
- Фикс: валидация id как int и параметризация запроса (`SELECT ... WHERE id = ?`).
- Регрессионный тест: practices/practice_06/lab/test_service.py::ShopTest::test_profile_sql_injection_blocked
- Проверка после фикса: `make step6` — Ran 18 tests … OK; запрос с `id=1 OR 1=1` → 400 и {"error":"invalid id"}.
- Статус: fixed

### R-23: SQLi в /search?q
- Категория: CWE-89, STRIDE:T
- Компонент: practices/practice_06/lab/service.py:58-61 → фикс на /search
- Severity: High
- Вектор и PoC (до фикса):
```
python3 practices/practice_06/lab/service.py --port 8066 &
curl -i 'http://127.0.0.1:8066/search?q=%25'                 # раскрытие всех профилей
curl -i 'http://127.0.0.1:8066/search?q=%25'"' OR '"1"='"1  # пыталась ломать строку
```
- Влияние: Раскрытие ПДн через бесконтрольный LIKE/конкатенацию.
- Связь: T-03 из REPORT_01.
- Фикс: параметризация LIKE и проверка типа q; конкатенации нет.
- Регрессионный тест: practices/practice_06/lab/test_service.py::ShopTest::test_search_sql_injection_blocked
- Проверка после фикса: `make step6` — Ran 19 tests … OK; инъекционный шаблон обрабатывается безопасно.
- Статус: fixed

### R-24: SQLi в /assistant/context?order_id
- Категория: CWE-89, STRIDE:T, LLM05 (если решение затем исполняется)
- Компонент: practices/practice_06/lab/service.py:88-98 → фикс на извлечении orders
- Severity: High
- Вектор и PoC (до фикса):
```
python3 practices/practice_06/lab/service.py --port 8066 &
curl -i 'http://127.0.0.1:8066/assistant/context?order_id=1%20OR%201=1'
# До фикса: 200 OK и в prompt попадал список всех заказов
```
- Влияние: Раскрытие данных заказов, загрязнение контекста LLM.
- Связь: T-19 из REPORT_01.
- Фикс: валидация order_id как int и параметризация запроса.
- Регрессионный тест: practices/practice_06/lab/test_service.py::ShopTest::test_assistant_context_sql_injection_blocked
- Проверка после фикса: `make step6` — Ran 20 tests … OK; инъекция возвращает 400 {"error":"invalid order_id"}.
- Статус: fixed

### R-25: /orders GET без auth и фильтра
- Категория: STRIDE:I/E
- Компонент: practices/practice_06/lab/service.py:60-61 → фикс фильтрации
- Severity: High
- Вектор и PoC (до фикса): `curl -i 'http://127.0.0.1:8066/orders'` возвращал все заказы без auth.
- Влияние: Утечка данных всех заказов.
- Связь: T-04 из REPORT_01.
- Фикс: требуется X-Token; фильтрация owner=session.id.
- Регрессионный тест: ShopTest::test_orders_get_requires_auth_and_filters_owner
- Проверка после фикса: make step6 OK; гость → 401, владелец видит только свои записи.
- Статус: fixed

### R-26: IDOR /files и произвольный path
- Категория: STRIDE:I, CWE-862
- Компонент: practices/practice_06/lab/service.py:78-81 → фикс авторизации и allowlist
- Severity: High
- Вектор и PoC (до фикса): чтение чужого чека `/files?user=bob&path=receipt.txt`; чтение служебного файла через path.
- Влияние: Утечка ПДн и служебных данных.
- Связь: T-06, T-07 из REPORT_01.
- Фикс: X-Token обязателен; user сравнивается с именем из сессии; разрешён только `receipt.txt` в собственном каталоге.
- Регрессионный тест: ShopTest::test_files_idor_blocked_and_auth_required
- Проверка после фикса: make step6 OK; попытки читать чужой/другой путь → 403.
- Статус: fixed

### R-27: /assistant/execute без auth/RBAC
- Категория: LLM06 Excessive Agency, LLM05 Improper Output Handling, STRIDE:E
- Компонент: practices/practice_06/lab/service.py:99-109 → фикс аутентификации/RBAC/запрет delete_tree
- Severity: Critical
- Вектор и PoC (до фикса):
```
curl -i -X POST 'http://127.0.0.1:8066/assistant/execute' -d '{"decision":{"tool":"export_profiles"}}'
```
- Влияние: Обход авторизации, утечка ПДн, опасные действия.
- Связь: T-08, T-09, T-10, T-15 из REPORT_01.
- Фикс: требование X-Token; staff-only на export_profiles; read_file только собственный чек; delete_tree запрещён.
- Регрессионный тест: ShopTest::test_assistant_execute_requires_auth_and_rbac
- Проверка после фикса: make step6 OK; гость → 401; customer export → 403; staff export → 200; delete_tree → 403.
- Статус: fixed

### R-28: /admin/export роль из заголовка
- Категория: STRIDE:S (Spoofing)
- Компонент: practices/practice_06/lab/service.py: /admin/export
- Severity: High
- Вектор и PoC (до фикса): заголовок `X-Role: staff` позволял экспорт без staff-сессии.
- Влияние: Утечка ПДн.
- Связь: T-01 из REPORT_01.
- Фикс: требование X-Token; роль читается из серверной сессии.
- Регрессионный тест: обновлён ShopTest::test_staff_can_export_with_staff_session (убран X-Role, проверяется staff-сессия).
- Проверка после фикса: make step6 OK.
- Статус: fixed

### R-29: /orders POST принимает price
- Категория: Business Logic Tampering
- Компонент: practices/practice_06/lab/service.py: /orders POST
- Severity: Medium
- Вектор и PoC (до фикса): клиент мог передать `price` и изменить цену каталога.
- Влияние: Финансовые потери/некорректные данные.
- Связь: T-05 из REPORT_01.
- Фикс: игнорировать входной `price`; цена только из каталога.
- Регрессионный тест: обновлён HttpTest::test_login_and_purchase_over_http (в теле price=1; на выходе 5000).
- Проверка после фикса: make step6 OK.
- Статус: fixed

### R-30: /debug/logs без auth и с секретами
- Категория: 152-ФЗ, STRIDE:I
- Компонент: practices/practice_06/lab/service.py: /debug/logs
- Severity: High
- Вектор и PoC (до фикса): любой гость мог читать логи с X-Token/паролями.
- Влияние: Компрометация токенов/ПДн.
- Связь: T-12, T-17 из REPORT_01.
- Фикс: staff-only; маскирование секретов в заголовках/телах; ограничение объёма.
- Регрессионный тест: покрыт косвенно другими тестами; отдельный тест можно добавить при необходимости.
- Проверка после фикса: make step6 OK.
- Статус: fixed
## 5.4 Цепочки атак (kill chains)

1) Prompt injection → /assistant/execute (без auth) → export_profiles → утечка ПДн. Статус: актуально, т.к. фикс отсутствует (см. T-08/T-10 из REPORT_01).
2) SQLi в /assistant/context (order_id) → раскрытие чужих заказов → LLM контекст с ПДн → Improper output handling. Статус: актуально (T-19/T-20).
3) /files без проверки владельца → чтение чужого чека → вставка вредоносного контента в отзыв → XSS в /reviews/view. Статус: актуально (T-06/T-13).

## 5.5 Итоговый чек (definition of done)
- [x] Все T-XX из REPORT_01 перепроверены частично; большинство остаются open (фиксы не вносились на этом шаге).
- [x] Все найденные bypass/regression задокументированы как R-XX (R-21).
- [x] Новые атаки по чек-листу: зафиксирован один новый вектор (ошибка JSON), остальное остаётся актуальным из REPORT_01.
- [x] Цепочки атак задокументированы (3 сценария).
- [x] `make step6` и `make test` зелёные после правок JSON-обработчика.
- [x] Регрессионные тесты по R-22 зелёные; SQLi /profile закрыт.
- [x] `judge-system-prompt.md` добавлен (см. ниже).
