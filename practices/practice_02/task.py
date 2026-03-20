import json
import os
from typing import List

"""
ПРАКТИКА 2: ПРОФЕССИОНАЛЬНЫЙ ПРОМПТИНГ (R.C.T.F.)
Курс: AI-инструменты в жизни инженера (ИТМО)

ИНСТРУКЦИЯ:
В этой практике мы учимся не просто "болтать" с AI, а программировать его поведение
с помощью фреймворка R.C.T.F. (Role, Context, Task, Format).
"""

# =================================================================================================
# 1. ИНФОРМАЦИЯ
# =================================================================================================
STUDENT_INFO = {
    "full_name": "Черных Арсений",
    "group_number": "M3303",
    "date": "2026-02-20"
}

# =================================================================================================
# 2. ЖУРНАЛ R.C.T.F. (Самая важная часть!)
# =================================================================================================
class RCTF_Log:
    def __init__(self, task_name: str, role: str, context: str, task: str, format_instruction: str, result: str):
        self.task_name = task_name
        self.role = role             # R: Кто такой AI? (Senior QA, Architect...)
        self.context = context       # C: Контекст проекта (Веб-сервис, Python, FastAPI...)
        self.task = task             # T: Что конкретно сделать?
        self.format = format_instruction # F: В каком виде выдать ответ? (Markdown, Gherkin...)
        self.result = result         # Итог (кратко)

PROMPT_LOGS: List[RCTF_Log] = [
    # TODO: Заполните лог для каждого задания
    # Пример:
    # RCTF_Log(
    #     task_name="Gherkin Scenarios",
    #     role="Senior QA Engineer",
    #     context="Проект погодного сервиса, пользователь хочет подписаться через API.",
    #     task="Напиши сценарии для фичи подписки.",
    #     format="Gherkin syntax (Given/When/Then)",
    #     result="Сгенерировал 3 сценария для API endpoints, но забыл негативные кейсы."
    # )
]

# =================================================================================================
# 3. АРТЕФАКТЫ (Улучшенные версии из Практики 1)
# =================================================================================================

# Задание 1: Улучшенная Архитектура (Mermaid v2)
MERMAID_V2 = """
C4Component
title WeatherService — Caching + Subscriptions (C4 Component)

Person(client, "Client", "Web/Mobile/Service consumer")

System_Boundary(ws, "WeatherService") {
  Container(fastapi, "FastAPI App", "Python / FastAPI", "REST API: subscriptions, weather lookup, notifications trigger")

  ContainerDb(redis, "Redis", "Redis", "Weather cache (TTL 10 minutes)\nKey: weather:{location}:{units}\nValue: forecast JSON + metadata")

  ContainerDb(pg, "PostgreSQL", "PostgreSQL", "Stores users & subscriptions")
  
  Component(usersTbl, "users", "Table", "Users registry\nid (PK), email, timezone, created_at")
  Component(subsTbl, "subscriptions", "Table", "User subscriptions to weather alerts\nid (PK), user_id (FK->users.id), location, conditions, cadence, is_active, created_at")

  Rel(pg, usersTbl, "contains", "SQL")
  Rel(pg, subsTbl, "contains", "SQL")
  Rel(subsTbl, usersTbl, "FK user_id → users.id", "SQL constraint")
}

System_Ext(weatherApi, "External Weather API", "3rd-party provider")

Rel(client, fastapi, "Uses WeatherService API", "HTTP REST/JSON")

Rel(fastapi, redis, "Read-through cache:\nGET weather by key\nMISS → fetch external → SETEX 600s", "Redis protocol (TCP)")
Rel(fastapi, weatherApi, "Fetch weather on cache miss", "HTTP REST/JSON")

Rel(fastapi, pg, "Manage users/subscriptions:\nCRUD, queries for active subscriptions", "SQL over TCP")

%% Optional: explain the cache flow more explicitly as a note-like component
Component(cachePolicy, "Cache Policy", "Logic", "TTL=600s\n- Try Redis first\n- On MISS call Weather API\n- Store response in Redis\n- Return to client")
Rel(fastapi, cachePolicy, "Implements", "Internal call")
Rel(cachePolicy, redis, "SETEX 600s", "Redis protocol")
Rel(cachePolicy, weatherApi, "GET /forecast", "HTTP REST/JSON")
"""

# Задание 2: Gherkin Scenarios (BDD)
GHERKIN_SCENARIOS = """
Feature: Управление подписками на уведомления о погоде через REST API
  Как пользователь сервиса
  Я хочу зарегистрироваться и создать подписку на погоду
  Чтобы получать уведомления по выбранному городу

  Scenario: Успешное создание подписки через API
    Given пользователь с email "user@example.com" не существует в системе
    And внешний Weather API возвращает данные для города "Helsinki"
    When клиент отправляет POST запрос на "/subscriptions" с телом:
      '''
      {
        "email": "user@example.com",
        "city": "Helsinki",
        "conditions": ["temperature_below_0"],
        "cadence": "daily"
      }
      '''
    Then сервис возвращает HTTP статус 201
    And в PostgreSQL создается запись в таблице "users"
    And в PostgreSQL создается запись в таблице "subscriptions"
    And Redis кэш обновляется для ключа "weather:Helsinki"

  Scenario: Ошибка при создании подписки — город не найден
    Given пользователь с email "user2@example.com" не существует в системе
    And внешний Weather API не содержит данных для города "UnknownCity"
    When клиент отправляет POST запрос на "/subscriptions" с телом:
      '''
      {
        "email": "user2@example.com",
        "city": "UnknownCity",
        "conditions": ["rain"],
        "cadence": "daily"
      }
      '''
    Then сервис возвращает HTTP статус 404
    And тело ответа содержит сообщение "City not found"
    And запись в таблице "subscriptions" не создается

  Scenario: Ошибка при создании подписки — email уже подписан
    Given пользователь с email "user@example.com" уже существует в системе
    And у пользователя уже есть активная подписка на город "Helsinki"
    When клиент отправляет POST запрос на "/subscriptions" с телом:
      '''
      {
        "email": "user@example.com",
        "city": "Helsinki",
        "conditions": ["temperature_below_0"],
        "cadence": "daily"
      }
      '''
    Then сервис возвращает HTTP статус 409
    And тело ответа содержит сообщение "Subscription already exists"
    And новая запись в таблице "subscriptions" не создается

    Feature: Добавление города в подписку на уведомления о погоде
  Как пользователь сервиса
  Я хочу добавить город в свою подписку
  Чтобы получать уведомления о текущей погоде

  Scenario: Успешное добавление города в подписку через API
    Given пользователь с email "user@example.com" уже зарегистрирован
    And у пользователя нет подписки на город "Helsinki"
    And внешний Weather API возвращает данные для города "Helsinki"
    When клиент отправляет POST запрос на "/subscriptions/cities" с телом:
      '''
      {
        "email": "user@example.com",
        "city": "Helsinki"
      }
      '''
    Then сервис возвращает HTTP статус 200
    And в PostgreSQL создается запись о подписке на город "Helsinki" для пользователя
    And Redis кэш обновляется для ключа "weather:Helsinki"

  Scenario: Ошибка при добавлении города — город не найден
    Given пользователь с email "user@example.com" уже зарегистрирован
    And внешний Weather API не содержит данных для города "UnknownCity"
    When клиент отправляет POST запрос на "/subscriptions/cities" с телом:
      '''
      {
        "email": "user@example.com",
        "city": "UnknownCity"
      }
      '''
    Then сервис возвращает HTTP статус 404
    And тело ответа содержит сообщение "City not found"
    And запись о подписке не создается

  Scenario: Ошибка при добавлении города — пользователь уже подписан
    Given пользователь с email "user@example.com" уже зарегистрирован
    And у пользователя уже есть подписка на город "Helsinki"
    When клиент отправляет POST запрос на "/subscriptions/cities" с телом:
      '''
      {
        "email": "user@example.com",
        "city": "Helsinki"
      }
      '''
    Then сервис возвращает HTTP статус 409
    And тело ответа содержит сообщение "City already subscribed"
    And новая запись о подписке не создается
"""

# Задание 3: Улучшенные DoR и DoD v2.0
DOR_V2 = """
# Definition of Ready (DoR) v2.0 — WeatherService

## Requirements (Требования)
- [ ] User Story оформлена в формате: "Как [роль], я хочу [действие], чтобы [ценность]"
- [ ] Бизнес-ценность задачи явно описана и согласована с Product Owner
- [ ] Определены границы задачи (in scope / out of scope)
- [ ] Acceptance Criteria заданы в формате BDD (Gherkin) и содержат ≥3 сценариев
- [ ] Определены основные пользовательские потоки (happy path + edge cases)
- [ ] Указаны ограничения (rate limits, SLA, TTL кэша и т.д.)
- [ ] Все зависимости от внешних систем задокументированы
- [ ] Задача декомпозирована до размера, выполнимого за 1 спринт

---

## Technical (Технические аспекты)
- [ ] Определены компоненты системы (FastAPI, Redis, PostgreSQL, внешние API)
- [ ] Описана стратегия кэширования (ключи, TTL, invalidation policy)
- [ ] Указаны требования к производительности (latency, throughput)
- [ ] Определены требования к отказоустойчивости (retry, fallback)
- [ ] Указаны ограничения внешнего Weather API (rate limit, quotas)
- [ ] Определены схемы хранения данных (таблицы users, subscriptions)
- [ ] Указаны требования к безопасности (валидация, auth, защита от XSS/SQLi)
- [ ] Есть предварительная оценка сложности (story points)

---

## Design (Дизайн API / Контракты)
- [ ] Определены REST endpoints (методы, URL)
- [ ] Описаны request/response модели (JSON schema)
- [ ] Определены HTTP статус-коды для всех сценариев
- [ ] Описаны ошибки и формат error response
- [ ] Указана идемпотентность операций (где применимо)
- [ ] Описана схема версионирования API (v1, v2 и т.д.)
- [ ] Контракты согласованы с frontend/клиентами
- [ ] Подготовлены примеры запросов и ответов

---

## Testing (Тестирование)
- [ ] Определены тест-кейсы на основе acceptance criteria
- [ ] Подготовлены unit-тесты для бизнес-логики
- [ ] Подготовлены интеграционные тесты (API + БД + Redis)
- [ ] Определены сценарии негативного тестирования
- [ ] Проверены edge cases (пустые данные, дубликаты, ошибки API)
- [ ] Определены требования к тестовым данным
- [ ] Проверена стратегия мокирования внешнего Weather API
- [ ] Указаны критерии приемки (Definition of Done link)

---

## Documentation (Документация)
- [ ] Обновлена OpenAPI/Swagger документация
- [ ] Добавлены примеры использования API
- [ ] Описаны изменения в архитектуре (если есть)
- [ ] Обновлены схемы (C4/sequence diagrams)
- [ ] Добавлены инструкции по локальному запуску
- [ ] Описаны переменные окружения и конфигурация
- [ ] Обновлены README / Wiki проекта
- [ ] Добавлены заметки для QA и поддержки (known limitations)
"""

DOD_V2 = """
# Definition of Done (DoD) v2.0 — WeatherService

## Requirements (Требования)
- [ ] Все Acceptance Criteria выполнены полностью (без частичной реализации)
- [ ] Реализованы все сценарии: happy path + негативные кейсы
- [ ] Поведение системы соответствует бизнес-логике User Story
- [ ] Нет открытых блокирующих багов (severity High/Critical)
- [ ] Граничные случаи (edge cases) обработаны
- [ ] Реализация соответствует согласованному scope (без лишнего функционала)
- [ ] Все зависимости (внешние API, сервисы) корректно интегрированы
- [ ] Product Owner принял задачу (acceptance подтвержден)

---

## Technical (Технические аспекты)
- [ ] Интеграция с PostgreSQL стабильна (CRUD операции работают корректно)
- [ ] Нет утечек соединений (DB pool, Redis connections)
- [ ] Redis-кэш используется согласно стратегии (TTL, ключи, invalidation)
- [ ] Реализована обработка отказов внешнего Weather API (retry/fallback)
- [ ] Соблюдены требования по производительности (latency/SLA)
- [ ] Логирование покрывает ключевые бизнес-события и ошибки
- [ ] Реализован health-check endpoint (/health)
- [ ] Приложение стабильно работает под нагрузкой (базовый sanity check)

---

## Design (Дизайн API / Контракты)
- [ ] Все API endpoints реализованы согласно спецификации
- [ ] Request/Response соответствуют JSON schema / контрактам
- [ ] HTTP статус-коды корректны для всех сценариев
- [ ] Ошибки возвращаются в стандартизированном формате (error model)
- [ ] Валидация входных данных реализована (schema validation)
- [ ] Идемпотентность соблюдена там, где требуется
- [ ] API не ломает backward compatibility (или версия увеличена)
- [ ] Swagger/OpenAPI полностью отражает текущее состояние API

---

## Testing (Тестирование)
- [ ] Покрыты unit-тестами основные бизнес-функции
- [ ] Покрыты интеграционные тесты (FastAPI + DB + Redis)
- [ ] Реализованы негативные тест-кейсы (ошибки, невалидные данные)
- [ ] Проверены edge cases (дубликаты, пустые значения, race conditions)
- [ ] Используются моки для внешнего Weather API
- [ ] Все тесты проходят успешно (CI pipeline green)
- [ ] Проведено ручное тестирование ключевых сценариев
- [ ] Регрессия не сломана (старый функционал работает)

---

## Documentation (Документация)
- [ ] Swagger/OpenAPI обновлен и доступен
- [ ] README содержит актуальные инструкции по запуску
- [ ] Описаны переменные окружения (env config)
- [ ] Добавлены примеры API-запросов и ответов
- [ ] Обновлены архитектурные схемы (при изменениях)
- [ ] Документированы изменения в кэшировании/БД
- [ ] Добавлены заметки для QA (как тестировать фичу)
- [ ] Добавлены known issues / ограничения (если есть)
"""

# Задание 4: Тест-план v2 (Классифицированный)
TEST_PLAN_V2 = """
| Test ID          | Level       | Preconditions                                                                                                                                               | Steps                                                                                                                                                                                                                                                                                                             | Expected Result                                                                                                                                                                                                                                                                    |
| ---------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UT-VAL-001       | Unit        | 1) Есть функция `validate_city(city: str) -> NormalizedCity/ValidationError` (или аналог). 2) Известный список допустимых форматов (латиница/пробел/дефис). | 1) Вызвать `validate_city("  Helsinki ")` 2) Вызвать `validate_city("New-York")` 3) Вызвать `validate_city("")` и `validate_city("!!!")`                                                                                                                                                                          | 1) Корректные значения нормализуются (trim, возможно title-case) и проходят. 2) Пустая строка/некорректные символы → `ValidationError` (или исключение) с ожидаемым кодом/сообщением.                                                                                              |
| UT-CACHE-002     | Unit        | 1) Есть функция `get_weather(city)` которая использует Redis read-through cache. 2) Redis client замокан. 3) Weather API client замокан. TTL = 600 сек.     | 1) Настроить mock Redis `GET` → HIT (вернуть JSON) 2) Вызвать `get_weather("Helsinki")` 3) Проверить, что Weather API client НЕ вызывался 4) Настроить mock Redis `GET` → MISS 5) Вызвать `get_weather("Helsinki")` 6) Проверить вызов Weather API и `SETEX(key, 600, value)`                                     | 1) При HIT возвращаются данные из Redis без обращения к Weather API. 2) При MISS выполняется запрос в Weather API, ответ кэшируется через `SETEX` на 600 сек и возвращается вызывающему коду.                                                                                      |
| IT-API-REDIS-003 | Integration | 1) Поднят тестовый Redis (docker/compose). 2) Поднят FastAPI в тестовом окружении. 3) Weather API замокан на уровне HTTP (wiremock/responses). 4) Кэш пуст. | 1) Выполнить `GET /weather/Helsinki` 2) Убедиться, что внешний Weather API был вызван 1 раз 3) Выполнить `GET /weather/Helsinki` повторно 4) Проверить, что внешний Weather API НЕ был вызван второй раз 5) (Опционально) Проверить TTL ключа в Redis > 0 и ≤ 600                                                 | 1) Первый запрос: 200 OK, данные соответствуют мок-ответу Weather API. 2) Второй запрос: 200 OK, данные идентичны, внешнего вызова нет (ответ из Redis). 3) В Redis существует ключ `weather:Helsinki` (или по вашему формату) с TTL около 600 сек.                                |
| IT-PG-SUBS-004   | Integration | 1) Поднята тестовая PostgreSQL (миграции применены). 2) FastAPI доступен. 3) Уникальный email для теста.                                                    | 1) Отправить `POST /subscribe` с телом `{ "email": "qa1@example.com", "city": "Helsinki" }` 2) Проверить ответ API 3) Сделать прямой запрос к БД: `SELECT * FROM users WHERE email=...` 4) `SELECT * FROM subscriptions WHERE user_id=... AND city='Helsinki'` 5) Повторить `POST /subscribe` с тем же email+city | 1) Первый POST: 201 Created (или 200 — по контракту), возвращается id/детали подписки. 2) В БД создан `users` и `subscriptions`, связи корректны. 3) Повторный POST: 409 Conflict (или ожидаемый код) и новая запись в `subscriptions` не появляется.                              |
| E2E-FLOW-005     | E2E         | 1) Развернут сервис целиком: FastAPI + PostgreSQL + Redis. 2) Weather API стаб/мок доступен. 3) Тестовый пользователь не существует.                        | 1) `POST /subscribe` `{ "email": "e2e1@example.com", "city": "Helsinki" }` 2) Проверить 201/200 3) `GET /weather/Helsinki` 4) Проверить 200 и корректную структуру payload 5) Повторить `GET /weather/Helsinki`                                                                                                   | 1) Подписка создается, возвращается подтверждение. 2) Погода по городу возвращается корректно. 3) Повторный `GET` обслуживается быстрее/без внешнего вызова (косвенно: по логам/метрикам или по счетчику вызовов мока Weather API = 1).                                            |
| E2E-NEG-006      | E2E         | 1) Сервис поднят целиком. 2) Weather API мок настроен: неизвестный город → 404. 3) Redis/PG доступны.                                                       | 1) `POST /subscribe` `{ "email": "e2e2@example.com", "city": "UnknownCity" }` 2) Проверить ответ 404 (или согласованный код) 3) `GET /weather/UnknownCity` 4) Проверить 404 5) Проверить, что в БД нет подписки на UnknownCity для этого email                                                                    | 1) Подписка на несуществующий город не создается. 2) API возвращает корректный статус и сообщение ошибки (например, `City not found`). 3) В БД отсутствуют записи подписки (и/или пользователь не создан — в зависимости от правил). 4) В Redis не появляется ключ по UnknownCity. |

"""

# Задание 5: Улучшенный Functional Delivery v2.0
FUNCTIONAL_DELIVERY_V2 = """
# WeatherService v1.0 — Jira Tickets (v2.0)

---

## 1) Title: Setup FastAPI Project Structure

**Description:**  
Инициализировать базовую структуру backend-приложения на FastAPI.  
Настроить роутинг, конфигурацию приложения, базовый health-check endpoint, Swagger/OpenAPI.  
Подготовить проект к масштабированию (разделение на modules: api, services, db, core).

**Acceptance Criteria (BDD):**
- Given приложение запущено локально  
  When пользователь открывает `/docs`  
  Then Swagger UI доступен и отображает endpoints  

- Given приложение запущено  
  When выполняется GET `/health`  
  Then возвращается HTTP 200 и `{ "status": "ok" }`  

- Given корректная конфигурация окружения  
  When приложение стартует  
  Then не возникает runtime ошибок  

- Given структура проекта  
  When разработчик открывает репозиторий  
  Then код разделен на слои (api/services/db)  

**Test Cases:**
- TC1: Запуск приложения → нет ошибок в логах  
- TC2: GET `/health` → 200 OK, корректный JSON  
- TC3: Открытие `/docs` → Swagger доступен  
- TC4: Проверка структуры проекта (наличие модулей)  
- TC5: Негативный — запуск без env → ошибка конфигурации  

**Dependencies:**  
- Нет  

**Priority:** High  
**Estimate:** 3 story points  

---

## 2) Title: Implement PostgreSQL Integration

**Description:**  
Настроить подключение к PostgreSQL.  
Реализовать модели `User` и `Subscription`.  
Подключить ORM (например, SQLAlchemy), реализовать миграции (Alembic).

**Acceptance Criteria (BDD):**
- Given корректные параметры подключения к БД  
  When приложение стартует  
  Then соединение с PostgreSQL устанавливается  

- Given применены миграции  
  When проверяется база данных  
  Then таблицы `users` и `subscriptions` существуют  

- Given пользователь создается через сервис  
  When выполняется операция сохранения  
  Then запись появляется в таблице `users`  

- Given подписка создается  
  When выполняется insert  
  Then запись появляется в `subscriptions` с корректным FK  

**Test Cases:**
- TC1: Проверка подключения к БД при старте  
- TC2: Применение миграций → таблицы созданы  
- TC3: Insert user → запись в БД  
- TC4: Insert subscription → корректная связь  
- TC5: Select данные → корректное чтение  
- TC6: Негативный — неверный DSN → ошибка подключения  
- TC7: Негативный — нарушение FK → ошибка  
- TC8: Проверка rollback транзакции  

**Dependencies:**  
- Setup FastAPI Project Structure  

**Priority:** High  
**Estimate:** 5 story points  

---

## 3) Title: Implement Subscription API

**Description:**  
Реализовать REST API для управления подписками:  
- POST `/subscriptions`  
- GET `/subscriptions`  
- DELETE `/subscriptions/{id}`  

Добавить валидацию входных данных и обработку ошибок.

**Acceptance Criteria (BDD):**
- Given валидный email и город  
  When отправляется POST `/subscriptions`  
  Then возвращается HTTP 201 и подписка создается  

- Given пользователь имеет подписки  
  When выполняется GET `/subscriptions`  
  Then возвращается список подписок  

- Given существует подписка с id  
  When отправляется DELETE `/subscriptions/{id}`  
  Then возвращается HTTP 200 и запись удаляется  

- Given невалидный JSON  
  When отправляется POST запрос  
  Then возвращается HTTP 400  

- Given подписка уже существует  
  When отправляется повторный POST  
  Then возвращается HTTP 409  

**Test Cases:**
- TC1: POST валидные данные → 201 Created  
- TC2: GET список → корректный JSON массив  
- TC3: DELETE существующий id → 200 OK  
- TC4: DELETE несуществующий id → 404  
- TC5: POST невалидный email → 400  
- TC6: POST дубликат → 409  
- TC7: Проверка данных в БД после операций  
- TC8: Негативный — пустое тело запроса  

**Dependencies:**  
- Implement PostgreSQL Integration  

**Priority:** High  
**Estimate:** 8 story points  

---
"""

# =================================================================================================
# 4. ДОМАШНЕЕ ЗАДАНИЕ (опционально)
# =================================================================================================

# Улучшение Event Storming v2.0 (опционально)
HOMEWORK_EVENT_STORMING_V2 = """
TODO: (Опционально) Улучшенный Event Storming с использованием R.C.T.F.
Добавьте больше событий, уточните команды и акторов.
"""

# Улучшение Roadmap v2.0 (опционально)
HOMEWORK_ROADMAP_V2 = """
TODO: (Опционально) Улучшенный Roadmap с использованием R.C.T.F.
Детализируйте версии, добавьте метрики успеха для каждой версии.
"""

# Chain of Thought (многоэтапный промптинг)
HOMEWORK_MULTIPROMPT_TASK = """
TODO: Опишите задачу, которую вы разбили на шаги
"""

HOMEWORK_MULTIPROMPT_STEPS = """
TODO: Список шагов (3-5 штук)
"""

HOMEWORK_MULTIPROMPT_SEQUENCE = """
TODO: Последовательность промптов с результатами каждого шага
"""

HOMEWORK_MULTIPROMPT_RESULT = """
TODO: Финальный результат после всех шагов
"""

# =================================================================================================
# 5. РЕФЛЕКСИЯ
# =================================================================================================
REFLECTION = {
    "before_after": """
    На простой промт не всегда идет ответ, который нужен. На прошлой практике я долго сидел с mermaid диаграмми, 
    т.к. нейронка генерила код с ошибками в синтаксисе. При RCTF всё ок (совпадение ли? думаю, нет, т.к. структурированный запрос)
    Так же, при RCTF как будто ты сам больше понимаешь, что хочешь от ИИ 

    """,
    
    "hardest_part": "Самая тяжелая часть - Task. Нужно правильно задать вопросы, чтобы получить именно то что нужно и при этом не тратить кучу токенов",
}

# =================================================================================================
# ЭКСПОРТ
# =================================================================================================
def export_report():
    if "TODO" in STUDENT_INFO["full_name"]:
        print("❌ ОШИБКА: Заполните информацию о студенте.")
        return

    report = f"# Отчет по Практике 2: {STUDENT_INFO['full_name']}\n\n"
    report += "## 1. Анализ промптов R.C.T.F.\n\n"
    
    if not PROMPT_LOGS:
        report += "⚠️ Журнал пуст!\n"
    
    for log in PROMPT_LOGS:
        report += f"### {log.task_name}\n"
        report += f"**Role:** {log.role}\n"
        report += f"**Context:** {log.context}\n"
        report += f"**Task:** {log.task}\n"
        report += f"**Format:** {log.format}\n"
        report += f"**Результат:** {log.result}\n"
        report += "---\n"

    report += "## 2. Улучшенные артефакты\n\n"
    report += "### Mermaid v2\n```mermaid\n" + MERMAID_V2 + "\n```\n\n"
    report += "### Gherkin Scenarios\n```gherkin\n" + GHERKIN_SCENARIOS + "\n```\n\n"
    report += "### DoR v2.0\n" + DOR_V2 + "\n\n"
    report += "### DoD v2.0\n" + DOD_V2 + "\n\n"
    report += "### Test Plan v2\n" + TEST_PLAN_V2 + "\n\n"
    report += "### Functional Delivery v2.0\n" + FUNCTIONAL_DELIVERY_V2 + "\n\n"

    report += "## 3. Домашнее задание\n\n"
    if HOMEWORK_EVENT_STORMING_V2 and "TODO" not in HOMEWORK_EVENT_STORMING_V2:
        report += "### Event Storming v2.0\n" + HOMEWORK_EVENT_STORMING_V2 + "\n\n"
    if HOMEWORK_ROADMAP_V2 and "TODO" not in HOMEWORK_ROADMAP_V2:
        report += "### Roadmap v2.0\n" + HOMEWORK_ROADMAP_V2 + "\n\n"
    if HOMEWORK_MULTIPROMPT_TASK and "TODO" not in HOMEWORK_MULTIPROMPT_TASK:
        report += "### Chain of Thought\n"
        report += "**Задача:** " + HOMEWORK_MULTIPROMPT_TASK + "\n\n"
        report += "**Шаги:** " + HOMEWORK_MULTIPROMPT_STEPS + "\n\n"
        report += "**Последовательность:** " + HOMEWORK_MULTIPROMPT_SEQUENCE + "\n\n"
        report += "**Результат:** " + HOMEWORK_MULTIPROMPT_RESULT + "\n\n"
    
    report += "## 4. Рефлексия\n\n"
    report += f"**Before/After:** {REFLECTION['before_after']}\n\n"
    report += f"**Сложности:** {REFLECTION['hardest_part']}\n"

    os.makedirs("artifacts", exist_ok=True)
    with open("artifacts/report_p2.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ Отчет успешно сгенерирован: artifacts/report_p2.md")

if __name__ == "__main__":
    export_report()
