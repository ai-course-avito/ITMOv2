# Интеграционные тесты

Файл ведёт OpenCode. Обсудите с агентом содержание и проверьте предложенный diff. Все дополнения и исправления поручайте агенту в чате.

## Chain of Verification: План → Вопросы → Ответы → Финал

### План (Integration scope)

- Слой: `infrastructure`.
- Проверяем репозитории: корректный маппинг SQLAlchemy ORM <-> domain entities (UUIDv4, value objects), транзакционные границы.
- Проверяем интеграцию с Redis: read-through кэш для поиска/координат, TTL, инвалидация.
- БД: PostgreSQL (в тестах — временная БД или dockerized), миграции Alembic применяются в setup.
- Внешние API: мок httpx-клиентов (без реальных сетевых вызовов).

### Вопросы для самопроверки

- Проверяем ли bidirectional mapping: ORM -> domain и domain -> ORM (включая UUIDv4)? Да/Нет.
- Фиксируем ли поведение при несоответствии схемы (нарушение NOT NULL/unique)? Да/Нет.
- Тестируем ли TTL и инвалидацию Redis после изменения локации? Да/Нет.
- Гарантируем ли отсутствие запросов к внешнему геокодеру в интеграционных тестах (всё мокаем)? Да/Нет.

### Ответы

- Mapping: Да, round-trip сохранение/загрузка сравнивает domain-entity поля и типы.
- Схема: Да, тестируем UniqueViolation/IntegrityError на дубли и пустые значения.
- Redis: Да, проверяем заполнение кэша при первом обращении и истечение TTL.
- Внешние API: Да, httpx-клиент подменён stub-ом, проверяем, что вызовы не уходят в сеть.

### Финальный план тестов

- Репозитории:
  - test_repo_persists_and_loads_domain_entity_roundtrip
  - test_repo_enforces_unique_constraints_and_indexes
  - test_repo_maps_uuidv4_without_flush
- Redis интеграция:
  - test_cache_read_through_populates_and_returns_cached_value
  - test_cache_ttl_expiration_and_recompute
  - test_cache_invalidation_on_location_update
- httpx-клиент (мок):
  - test_geocoder_client_handles_timeouts_and_retries_without_network

Инфраструктура: docker-compose для PG/Redis или in-memory подходы; Alembic up + fixtures; pytest markers: integration.

## Как использовали AI

- Для чего: спланировать интеграционные проверки маппинга ORM<->domain и Redis-кэша без реальных сетевых вызовов.
- Тип промпта: Chain of Verification + RCTF.
- Строка в [`prompts.md`](prompts.md): P1-06.
- Что проверил студент и какие исправления поручил агенту: корректность сценариев, покрытие TTL/инвалидации, round-trip маппинга.
