Название: Mini Shop — модель угроз (этап 1)

1. Описание системы

- Компоненты
  - Клиент: пользовательские HTTP-клиенты (curl, браузер, тесты).
  - HTTP API: процесс Python (service.py) на 127.0.0.1, ThreadingHTTPServer.
  - Память процесса: сессии, логи, отзывы, каталог, конфигурация.
  - БД: SQLite in-memory (таблицы profiles, orders).
  - Файловая система стенда: временный каталог Sandbox (sandbox.py), в нём пользовательские чеки и служебная заметка.
  - LLM/планировщик: логический компонент. Вход — /assistant/context (формирование промпта), выполнение — /assistant/execute (инструменты read_file, export_profiles, delete_tree).

- Данные/активы
  - ПДн: profiles(id, name, email, address).
  - Заказы: orders(id, owner, product, price).
  - Секреты/служебные данные: private/operator-note.txt в Sandbox; токены X-Token; пароли в теле /login; system prompt и список инструментов.
  - Отзывы: произвольный пользовательский текст (включая потенциально вредный контент/инструкции для LLM).
  - Логи запросов: метод, путь, тело, заголовки (включая X-Token, пароли).

- Потоки данных
  - Клиент → API: HTTP JSON/HTML (логин, чтение профилей/заказов/файлов, публикация отзывов, LLM-контекст/исполнение).
  - API ↔ БД: SQL-запросы (часть строится на основе пользовательского ввода).
  - API ↔ FS(Sandbox): чтение/удаление файлов по путям из запроса/решения LLM.
  - API ↔ LLM: формирование промпта с данными заказа и отзывами; принятие JSON-решения и исполнение инструментов.
  - API → Память: записи в логи, хранение сессий и отзывов.

- Акторы
  - Аутентифицированный клиент (customer/staff).
  - Неаутентифицированный клиент (гость/злоумышленник).
  - Косвенный актор: модель LLM (может быть подвержена prompt injection через отзывы/вопрос).

1.a Инвентаризация API и I/O

- HTTP эндпоинты (метод, путь, параметры, аутентификация)
  - GET /health — без параметров, без аутентификации.
  - GET /products — без параметров, без аутентификации.
  - POST /login — JSON {username, password}, без аутентификации, возвращает {token}.
  - GET /profile — query id, без аутентификации, возвращает профиль по id.
  - GET /search — query q, без аутентификации, поиск по name LIKE.
  - GET /orders — без параметров, без аутентификации, возвращает все заказы.
  - POST /orders — JSON {product, optional price}, требуется X-Token, создаёт заказ.
  - GET /admin/export — без параметров, проверяет X-Role (ошибочно), возвращает все профили.
  - GET /files — query user, path, без аутентификации, читает файл из Sandbox.
  - POST /reviews — JSON {product, text}, без аутентификации, сохраняет отзыв.
  - GET /reviews/view — без параметров, без аутентификации, возвращает HTML отзывов.
  - GET /debug/logs — без аутентификации, возвращает журналы запросов.
  - GET /assistant/context — query order_id, question, без аутентификации, возвращает system prompt с данными.
  - POST /assistant/execute — JSON {decision:{tool, arguments}}, без аутентификации, исполняет инструмент.

- Точки чтения/записи файлов
  - Sandbox.read(path) — чтение файла (service.py L79-L80, L102-L104).
  - Sandbox.delete_tree(path) — удаление файлов/деревьев (service.py L106-L108).

- Вызовы LLM/внешних процессов
  - Формирование prompt в /assistant/context (service.py L88-L98).
  - Исполнение решения LLM в /assistant/execute (service.py L99-L109).

- Модели данных и хранение ПДн
  - SQLite :memory: — таблицы profiles(id, name, email, address) [ПДн]; orders(id, owner, product, price).
  - В памяти процесса: sessions, reviews, logs (могут содержать ПДн/секреты).

2. DFD (Mermaid)

```mermaid
flowchart TB
  subgraph ClientZone[Client]
    C[HTTP Client]
  end

  subgraph ServerZone[API Process]
    A[HTTP API\nservice.py]
    S[(Sessions, Reviews, Logs\nIn-memory)]
    DB[(SQLite :memory:\nprofiles, orders)]
    FS[(Sandbox FS\nreceipts, private note)]
    LLM[LLM Planner\n(prompt, decision JSON)]
  end

  %% Trust boundaries
  classDef boundary stroke-dasharray: 5 5
  class ClientZone boundary
  class ServerZone boundary

  C -- HTTP JSON/HTML --> A
  A <-- store/read --> S
  A <-- SQL --> DB
  A <-- read/delete --> FS
  A -- prompt --> LLM
  LLM -- decision(tool,args) --> A

  %% Tools executed by API
  A -. read_file/export_profiles/delete_tree .-> FS
  A -. export_profiles .-> DB
```

Trust boundaries
- Клиент ↔ API (основная граница недоверенного ввода).
- API ↔ БД (инъекции SQL, целостность данных).
- API ↔ Файловая система Sandbox (путь и доступ к файлам внутри стенда).
- API ↔ LLM (prompt/decision; риск prompt injection и опасных действий).
- Память процесса (логи/сессии/отзывы) — внутренняя зона, но содержит чувствительные данные.

3. STRIDE по компонентам (минимум по одной угрозе)

- HTTP API (service.py)
  - S: Подмена роли через заголовок X-Role в /admin/export (Spoofing).
  - T: SQL-инъекции в /profile, /search, /assistant/context (Tampering/Integrity).
  - R: Отсутствие аудита действий инструментов LLM и связи с субъектом (Repudiation).
  - I: Утечка ПДн через /admin/export, /profile, /search, /debug/logs, /files, /assistant/execute (Information Disclosure).
  - D: Удаление дерева файлов через /assistant/execute delete_tree и раздувание отзывов/логов (DoS).
  - E: Выполнение инструментов без авторизации (Elevation of Privilege).

- БД SQLite
  - S: Подмена идентификатора записи (IDOR) в /profile?id и /orders GET без аутентификации.
  - T: Изменение цены заказа через параметр price (Tampering, бизнес-логика).
  - R: Нет журналирования изменения заказов с привязкой к пользователю.
  - I: Извлечение всех профилей через SQLi/экспорт.
  - D: Тяжёлые запросы LIKE с неограниченным вводом.
  - E: Чтение чужих записей без проверки прав (горизонтальная эскалация).

- ФС Sandbox
  - S: Подмена пользователя через параметр user в /files.
  - T: Траверс внутри Sandbox (files/../private/...) для доступа к служебной заметке.
  - R: Нет аудита чтений/удалений файлов по субъекту.
  - I: Чтение чужих чеков и служебного файла.
  - D: Полное удаление каталога через delete_tree('.')
  - E: Доступ к операциям без проверки роли/владельца.

- Логи/Отзывы (in-memory)
  - S: Лёгкая имитация легитимного клиента без сессии в /debug/logs (нет auth).
  - T: Отзыв как носитель вредоносного контента для LLM.
  - R: Нет неизменяемых журналов/подписи событий.
  - I: В логах сохраняются токены/пароли/ПДн.
  - D: Неограниченный рост массивов logs/reviews.
  - E: XSS при просмотре отзывов в HTML.

- LLM-подсистема
  - S: Косвенная подмена инструкций через prompt injection в отзывах.
  - T: Некорректное решение может модифицировать/удалить данные.
  - R: Нет фиксации исходного решения и валидации подписи/происхождения.
  - I: Утечка system prompt и данных заказа в /assistant/context.
  - D: Unbounded prompt size из-за отзывов.
  - E: Excessive agency — инструменты исполняются без политик и привязки полномочий.

3.a STRIDE-таблица по компонентам

| Компонент | S (Spoofing) | T (Tampering) | R (Repudiation) | I (Info Disclosure) | D (DoS) | E (EoP) |
|---|---|---|---|---|---|---|
| HTTP API | X-Role spoof | SQLi в /profile,/search | Нет аудита инструментов | Экспорт/логи/файлы | delete_tree рост отзывов | Выполнение инструментов без auth |
| SQLite | IDOR id, /orders GET | price override | Нет аудита изменений | Извлечение профилей | Тяжёлые LIKE | Чтение чужих записей |
| FS Sandbox | user spoof | traversal внутри стенда | Нет аудита | Чужие чеки, private note | delete_tree('.') | Нет проверки ролей |
| Logs/Reviews | — | вредоносный контент | нет неизменяемости | токены/пароли в логах | рост массивов | XSS в обзоре |
| LLM | косвенное внедрение | опасные решения | нет фиксации решения | утечка system prompt | рост контекста | excessive agency |

4. LLM-специфика (OWASP LLM Top 10, 2025)

- LLM01 Prompt Injection: отзывами/вопросом можно навязать выполнение export_profiles/delete_tree/read_file.
- LLM02 Sensitive Info Disclosure: /assistant/context раскрывает структуру промпта и данные заказов; инструменты раскрывают ПДн и служебные файлы.
- LLM05 Improper Output Handling: решение LLM исполняется без валидации схемы/политик, без сопоставления с правами пользователя.
- LLM06 Excessive Agency: инструменты доступны без аутентификации и без ограничений по субъекту/ролям.
- LLM07 System Prompt Leakage: /assistant/context возвращает полный system prompt и список инструментов.
- LLM10 Unbounded Consumption: неограниченное число/размер отзывов ⇒ рост промпта и памяти.

5. Комплаенс 152-ФЗ (в контексте учебного стенда)

- Хранение ПДн: таблица profiles в RAM SQLite, также ПДн попадает в логи и может оказаться в промптах LLM и ответах API.
- Принципы минимизации: API выдаёт больше, чем необходимо (профили/заказы/логи без авторизации). Нарушение минимизации раскрытия и доступа по роли.
- Согласие субъекта: отсутствует механизм фиксации согласия на обработку ПДн.
- Сроки хранения: явно не регламентированы; логи и отзывы растут без ограничений.
- Локализация/доступ: данные остаются локально в процессе и на локальной ФС стенда; доступ не ограничен аутентификацией на ряде эндпоинтов.
- Логирование ПДн: в /debug/logs сохраняются тела запросов (включая пароли) и заголовки (токены).

6. Матрица «угроза → мера защиты → способ проверки»

- Spoofing роли в /admin/export → Игнорировать X-Role, использовать роль из серверной сессии; требовать staff-сессию → curl без токена должен получить 401/403; со staff-токеном — 200.
- SQLi в /profile, /search, /assistant/context → Параметризованные запросы (sqlite3.execute с ?), whitelisting типов для id → Запросы вида id=1 OR 1=1 должны возвращать 400; корректные id — 200.
- IDOR /files и чужие чеки → Привязка user к сессии, запрет относительных сегментов, allowlist подкаталога текущего пользователя → Чтение чужого чека должно давать 403.
- Удаление FS через delete_tree → Политики на инструмент: разрешать только владельцу собственный подкаталог; denylist опасных путей; подтверждение действий → Попытка delete_tree('.') должна дать 403.
- Логи с ПДн → Фильтрация/редакция чувствительных полей, защита /debug/logs авторизацией staff → Доступ без staff — 403; пароли/токены в логах отсутствуют.
- XSS в /reviews/view → Экранирование HTML или возврат JSON, Content Security Policy → Вставка <script> не выполняется/экранируется.
- Excessive Agency /assistant/execute → Обязательная аутентификация; сопоставление инструмента и аргументов с правами текущего пользователя; валидация схемы → Вызов инструмента без токена — 401; чтение чужого файла — 403.
- System Prompt Leakage → Не возвращать внутренний system prompt и список инструментов клиенту; формировать контекст минимально необходимый → В ответе отсутствуют внутренние подсказки/инструменты.
- Unbounded Consumption → Квоты/лимиты на длину отзывов и их количество; пагинация; ограничения на общую длину промпта → Большие вводы режутся/отклоняются 413/400.

6.a Покрытие угроз по T-ID (см. REPORT_01.md)

- T-01 (Spoofing X-Role) → Мера: роль только из сессии; staff-only. Проверка: curl с X-Role без токена → 401/403.
  (реализовано; см. R-28)
- T-02 (SQLi /profile) → Мера: параметризация и валидация id. Проверка: id='1 OR 1=1' → 400. (реализовано; см. R-22 и тест test_profile_sql_injection_blocked)
- T-03 (SQLi /search) → Мера: параметризация, экранирование wildcard, auth. Проверка: q="%' OR '1'='1" → 400.
  (реализовано; см. R-23 и тест test_search_sql_injection_blocked)
- T-04 (IDOR /orders GET) → Мера: auth и фильтр owner=session.id. Проверка: гость → 401; чужие заказы не видны.
  (реализовано; см. R-25 и тест test_orders_get_requires_auth_and_filters_owner)
- T-05 (Price override) → Мера: игнорировать client price. Проверка: price в теле не влияет на итог.
  (реализовано; см. R-29 и обновлённый HTTP-тест)
- T-06 (Files: чужие чеки) → Мера: user из сессии; allowlist. Проверка: user=bob для alice → 403.
  (реализовано; см. R-26 и тест test_files_idor_blocked_and_auth_required)
- T-07 (Private note) → Мера: запрет на private/* в API. Проверка: попытка чтения → 403.
- T-08 (Exec tools без auth) → Мера: обязательный токен и RBAC на инструменты. Проверка: POST без X-Token → 401.
- T-09 (delete_tree DoS) → Мера: запрет операции или ограничение до user root. Проверка: path='.' → 403.
- T-10 (export_profiles) → Мера: staff-only; минимизация полей. Проверка: customer → 403; staff → 200.
  (реализовано совместно через /assistant/execute; см. R-27 и тест test_assistant_execute_requires_auth_and_rbac)
- T-11 (System prompt leakage) → Мера: не возвращать системные инструкции и список инструментов. Проверка: ответ не содержит их.
- T-12 (Debug logs) → Мера: staff-only + редактирование секретов. Проверка: гость → 403; секреты маскированы.
  (реализовано; см. R-30)
- T-13 (XSS reviews) → Мера: HTML-экранирование/JSON. Проверка: <script> не исполняется.
- T-14 (Prompt Injection) → Мера: контент-фильтры/инструкции; политика инструментов. Проверка: вредоносный отзыв не приводит к опасному действию.
- T-15 (Improper output handling) → Мера: схема, авторизация и проверки контекста. Проверка: ручной JSON без прав → 401/403.
- T-16 (Unbounded consumption) → Мера: лимиты/пагинация. Проверка: длинные отзывы → 413/400; контекст усечён.
- T-17 (Secrets in logs) → Мера: маскирование; staff-only. Проверка: пароли/токены не видны в логах.
- T-18 (Profiles without auth) → Мера: требовать X-Token и фильтр по владельцу/роли. Проверка: гость → 401.
- T-19 (SQLi order_id) → Мера: параметризация и валидация int. Проверка: '1 OR 1=1' → 400.
  (реализовано; см. R-24 и тест test_assistant_context_sql_injection_blocked)
- T-20 (Context leaks order data) → Мера: auth + owner check; минимум данных. Проверка: чужой order_id → 403/404.

7. Принятые риски (для учебного стенда)

- Отсутствие TLS и работа на 127.0.0.1 — приемлемо для локальной лаборатории.
- Сессии в памяти без срока действия — допускается в рамках одноразового процесса.
- SQLite in-memory и временная FS — приемлемо для лабораторного сценария; данные не персистентны.
