# Research: логика ревью

Дата: 2026-10-27. Все решения в пределах CONTRACT.md v1.0 и заданного координатором стека; нерешённых проектных NEEDS CLARIFICATION нет. Реальный endpoint/model/key — параметры запуска, не повод выдумывать провайдера или заявлять живое демо. Research выполнен по исходникам/официальной документации; дополнительные агенты не создавались.

## Общий бюджет времени и отмена

**Decision**: Внешний await оборачивается в `asyncio.timeout(10)`; HTTPX также получает сетевые timeout. CancelledError не превращается в успешный результат и распространяется до HTTP-клиента. Автоматических retry нет.

**Rationale**: HTTPX различает connect/read/write/pool timeout; один read timeout не ограничивает всю операцию. Внешний async deadline обеспечивает общий бюджет, а асинхронный transport допускает отмену ожидания. Источники: [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/), [Python 3.13 timeout и cancellation](https://docs.python.org/3.13/library/asyncio-task.html#timeouts).

**Alternatives considered**: Только HTTPX timeout не выражает общий бюджет; синхронный вызов в thread затрудняет остановку ожидания и не нужен.

## HTTP boundary и проверка без сети

**Decision**: FastAPI request читается явно для согласованного порядка content type → JSON → shape/type → size → empty → diff → config. Сервис получает injectable adapter. unittest проверяет async service, HTTPX ASGITransport — HTTP API, MockTransport — upstream HTTP.

**Rationale**: Это сохраняет единый error envelope и точные 400/413/415/422; автоматическая типизация тела не должна подменить порядок либо преобразовать строки/boolean в допустимые значения. Transport abstractions официально поддерживают вызов ASGI приложения и mock upstream: [HTTPX transports](https://www.python-httpx.org/advanced/transports/).

**Alternatives considered**: Внешняя модель в каждом тесте недетерминирована и требует ключа. Отдельный тестовый сервер для unit/API не требуется; браузерные e2e запускает root.

## Конфигурация и интеграция UI

**Decision**: `app.api:app`; REVIEW_MODE=demo|live, default demo; REVIEW_LLM_URL — полный chat/completions endpoint, REVIEW_LLM_MODEL и REVIEW_LLM_KEY. Live требует все три настройки, иначе 503. GET / отдаёт static/index.html, /static/* отдаёт файлы команды UI.

**Rationale**: Default demo даёт воспроизводимый локальный запуск с обязательным mode=demo. Никакого изменения режима по входу и скрытого live→demo. Раздача статических файлов — штатная возможность FastAPI: [Static Files](https://fastapi.tiangolo.com/tutorial/static-files/).

**Alternatives considered**: CORS/отдельный frontend сервер увеличивают настройки без пользы одному экрану. Хранить ключ в браузере запрещено.

## Live adapter и demo

**Decision**: HTTPX AsyncClient отправляет один POST на настроенный endpoint с model и messages (system: правила/форма; user: очищенный diff как данные), Authorization Bearer из окружения; redirects и retries не включаются. Ожидается строка choices[0].message.content с JSON summary/risks/checks. Transport/status failures → MODEL_UNAVAILABLE, timeout → MODEL_TIMEOUT, неверный envelope/content/JSON → INVALID_MODEL_OUTPUT.

**Rationale**: Это минимальный совместимый chat/completions интерфейс без привязки SDK к провайдеру. Ответ не считается надёжным до общей проверки.

**Alternatives considered**: SDK или streaming не нужны выбранному scope. Провайдер не объявляется проверенным без реального запуска.

**Demo decision**: Детерминированно пройти реально разобранные добавленные строки и предложить до трёх замечаний только для показанных конструкций: извлечение payload["diff"] без видимой проверки, включение diff в prompt, вызов llm.generate(prompt). Каждое замечание цитирует найденную строку и объясняет проверку API-1, SEC-1 либо REL-1 как возможный риск, не утверждает устройство невидимого кода. Если совпадений нет — risks=[], непустые summary/checks. Это демонстрационные правила, не искусственный «реальный AI».

## Парсер и окончательная валидация

**Decision**: Парсер хранит строки с path, side, old/new координатами и точным prefixed text. Игнорирует declared counts, но не придумывает строки; сохраняет согласованные ограничения diff. Сначала маскируются строки входа с сохранением переносов; координатный индекс для evidence строится из очищенной версии. Строковые значения ответа рекурсивно маскируются после JSON parse, затем проверяются exact keys/types/lengths и соответствие evidence/path/line.

**Rationale**: TRAINING_PR.diff содержит частичные hunks. Последнее маскирование может изменить evidence, поэтому проверять только исходный ответ недостаточно. Смысловую истинность замечания этот процесс не доказывает.

**Alternatives considered**: Строгая проверка counts отклоняет обязательный учебный пример. RULE-only/null отвергнуты человеком в пользу одинаковой навигации каждого риска.
