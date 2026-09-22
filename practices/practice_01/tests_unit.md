# Тесты unit-уровня

Файл ведёт OpenCode. Обсудите с агентом содержание и проверьте предложенный diff. Все дополнения и исправления поручайте агенту в чате.

## Chain of Verification: План → Вопросы → Ответы → Финал

### План (Unit scope)

- Слои под тест: `domain` (entities, value objects, policies) и `application` (use-cases/services). Строго без БД/Redis/HTTP.
- Точки проверки domain:
  - Создание сущностей с UUIDv4 без обращения к БД (генерация ID в domain).
  - Иммутабельность value-объектов, инварианты координат (−90..90, −180..180) и нормализация названий (JP/EN).
  - Бизнес-правила: установка/снятие флага верификации, запрет повторной верификации без прав модератора.
- Точки проверки application:
  - Use-case поиска использует абстрактный порт `LocationsRepository` (mock) и нормализатор, не ходит в сеть/БД.
  - Use-case сохранения в избранное использует порт `FavoritesRepository` (mock) и валидирует уникальность пары user-location.
  - Кэш-стратегии не тестируются здесь; только оркестрация и предикаты.
- Инструменты: pytest, unittest.mock, freezegun (для таймштампов), hypothesis (по желанию) для свойств координат.

### Вопросы для самопроверки

- Покрываем ли мы генерацию UUIDv4 на уровне domain без `flush`? Да/Нет.
- Есть ли негативные кейсы по координатам и названиям (пустые строки, NaN, выход за диапазон)? Да/Нет.
- В application исключены ли любые побочные эффекты (БД, Redis, httpx)? Да/Нет.
- Проверяем ли, что сервисы используют только порты, а не конкретные реализации? Да/Нет.

### Ответы

- UUIDv4: Да, тесты проверяют, что `Location(id=None, ...)` присваивает `uuid4()` в конструкторе/фабрике.
- Негативные кейсы: Да, property-based тесты на диапазоны координат и пустые названия, ожидаем `ValueError`.
- Побочные эффекты: Да, все зависимости замоканы; тест упадёт при попытке импортировать infrastructure.
- Порты: Да, используем протоколы/интерфейсы и mock-объекты, проверяем вызовы и контракты.

### Финальный план тестов

- Domain Entities (dataclasses, slots=True):
  - test_location_creates_uuid_v4_without_db
  - test_location_coordinates_validation_ranges
  - test_location_title_normalization_jp_en
  - test_location_verify_requires_moderator_role
- Value Objects:
  - test_geo_point_is_hashable_and_equals
  - test_title_value_object_disallows_empty
- Application Services:
  - test_search_locations_uses_repository_port_and_normalizer
  - test_add_favorite_prevents_duplicates
  - test_add_favorite_requires_authenticated_user

Фикстуры: mock репозиториев, нормализатора названий; frozen time для меток модерации.

## Как использовали AI

- Для чего: спланировать unit-стратегию, сформировать список проверок и инвариантов без внешних зависимостей.
- Тип промпта: Chain of Verification + RCTF.
- Строка в [`prompts.md`](prompts.md): P1-06.
- Что проверил студент и какие исправления поручил агенту: соответствие unit-уровню, покрытие инвариантов, отсутствие побочных эффектов.
