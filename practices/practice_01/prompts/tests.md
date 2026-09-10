# MASTER PROMPT №4: Тестирование

## 01. Goal + Role
Goal: описать четыре уровня тестирования для AI-агента code review:
unit, integration, load, e2e — с проверяемыми шагами и ожидаемыми
пределами.

Role: ты — QA Lead + DevOps-инженер. Ты умеешь писать unit-тесты,
настраивать интеграционные проверки с моками, проектировать
нагрузочные сценарии и описывать e2e-сценарии.

## 02. Inputs + Sources
- adr.md — архитектура и компоненты
- product_management.md — user stories и use cases
- analysis.md — процесс TO BE
- context.md — стек и ограничения

## 03. Context Pack
[ВСТАВЬ adr.md]
[ВСТАВЬ product_management.md]
[ВСТАВЬ analysis.md]
[ВСТАВЬ релевантные выдержки из context.md]

## 04. Task + Deliverables
Создай ЧЕТЫРЕ артефакта:

1. tests_unit.md — 3–5 unit-тестов:
   - Что тестируем (функция/модуль)
   - Код теста (pytest/unittest)
   - Моки (OpenRouter, БД)
   - Ожидаемый результат

2. tests_integration.md — 3–5 интеграционных тестов:
   - С какими внешними системами (GitHub API, OpenRouter, БД)
   - Как поднимается окружение (docker-compose)
   - Что проверяется (запрос/ответ, коды, ошибки)
   - Использование моков

3. tests_load.md — нагрузочные сценарии:
   - 3 уровня: базовый / пиковый / стресс
   - RPS, время ответа (p50, p95, p99), память
   - Поведение при перегрузке (очередь, 503, retries)
   - Инструмент (k6 / Locust / JMeter) и обоснование

4. tests_e2e.md — 3 сквозных сценария:
   - Happy path: PR → AI → комментарий → merge
   - Альтернатива: модель вернула ошибку → уведомление
   - Исключение: огромный PR → graceful degradation
   - Для каждого: вход, шаги, ожидаемый результат

## 05. Output Format
- Четыре отдельных Markdown-файла.
- В tests_unit.md и tests_integration.md код в блоках
  ```python … ``` с описанием «Что проверяем / Моки / Ожидаемо».
- В tests_load.md — Markdown-таблица с RPS/временем/памятью.
- В tests_e2e.md — заголовки `### E2E-0X` с полями
  Предусловие / Вход / Шаги / Ожидаемый результат.
- В каждом файле — раздел «Как использовали AI».

## 06. Allowed / Forbidden / Workflow / Stop / Verification / DoD

Allowed:
- Использовать моки для внешних API.
- Указывать конкретные цифры для нагрузки.
- Ссылаться на adr.md при выборе компонентов.

Forbidden:
- Реальные API-ключи в тестах.
- Смешивать unit и integration тесты в одном файле.
- Требовать реальную инфраструктуру для тестов.
- Оставлять сценарии без ожидаемого результата.

Workflow:
1. Прочитай adr.md — выдели компоненты для тестов.
2. Напиши unit-тесты для ключевых функций.
3. Опиши integration-тесты с моками и docker-compose.
4. Спроектируй 3 уровня нагрузки с цифрами.
5. Опиши 3 e2e-сценария (happy / alternative / exception).
6. Прогони самопроверку по DoD.

Stop:
- Если для теста нужен реальный API-ключ — замени на мок.
- Не переходи к сквозному code review — это промпт №5.

Verification:
- В tests_unit ≥3 теста с моками.
- В tests_integration ≥3 теста и описание окружения.
- В tests_load указаны цифры RPS/времени/памяти.
- В tests_e2e покрыты happy / alternative / exception.

DoD:
- [ ] Созданы 4 файла tests_*.md
- [ ] Unit: ≥3 теста, изолированы
- [ ] Integration: ≥3 теста, есть docker-compose
- [ ] Load: 3 уровня нагрузки, есть цифры
- [ ] E2E: 3 сценария, покрыты happy + alternative + exception
- [ ] В каждом файле есть «Как использовали AI»