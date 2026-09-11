# tests_load.md

## 1. Назначение (Для чего)
Цель документа — описать практические сценарии нагрузочного тестирования и критерии успеха для сервиса, обрабатывающего diffs. Нагружаем основной API endpoint для малых и пограничных диффов, а также проверяем поведение при включённой задержке LLM. Успех определяется соответствием измеренных метрик целевым SLO/SLA: пороги для p95, допустимые уровни error rate, отсутствие 5xx, контролируемые timeouts, подтверждённые воспроизводимыми evidence (сводки/графики).

## 2. Область и система под тестом
- product_name: <Название продукта/сервиса>
- base_url: <URL стенда/окружения>
- endpoint_under_test: <Основной endpoint под нагрузкой, например POST /api/v1/review>
- auth: <Схема аутентификации/заголовки, если нужны>
- llm_latency_toggle: <Как включается/эмулируется задержка LLM: фича-флаг/заглушка/параметр>
- data_shape_small: <Описание small diff: <1K символов, типовые поля, пример генерации входных данных>>
- data_shape_large: <Описание large diff: ~20 000 символов, как формируется, граничные поля>
- monitoring: <Как собираются метрики ресурсов (CPU/RAM/GC), если доступно; иначе «n/a»; TODO-интеграция>

Оговорки/исключения:
- Тестируем только endpoint_under_test. Внешние интеграции и UI вне области теста.
- Сети/балансировщики рассматриваются как “as is”, дополнительные профили сетевых сбоёв не включены.

## 3. Метрики и цели (SLO/SLA)
Определения:
- p95/p99: 95-й/99-й перцентили времени ответа, измеряются на уровне HTTP-запросов.
- error rate: доля ошибочных запросов (HTTP 4xx/5xx и сетевые ошибки), %.
- 5xx: доля ответов 5xx, %; целевое значение — 0%.
- timeouts: доля запросов, завершённых по тайм-ауту клиента/прокси/серверу (например, 408/504 или client-side timeout), %.
- Ресурсы (опционально): CPU/RAM/GC на сервисе, если monitoring подключён.

Сводная таблица целей (SLO/SLA):
| Сценарий | Профиль RPS | Длительность (warmup/ramp/steady) | p95 (цель) | error rate (цель) | 5xx (цель) | timeouts (цель) |
|---|---|---|---|---|---|---|
| S1: Малый diff | 5–10 (steady 8) | 2 мин / 2 мин / 10 мин | < 500 мс | < 1% | 0% | 0% |
| S2: Пограничный diff | 2–5 (steady 3–4) | 3 мин / 3 мин / 12 мин | < 10 с (REL-1) | < 1% | 0% | < 1% |
| S3: Задержка LLM | 1–2 (steady 1–2) | 2 мин / 2 мин / 10 мин | — (фиксация) | < 1% | 0% | ≤ 1% (контролируемые) |

Примечание: p99 во всех сценариях фиксируется и прилагается в evidence, но в SLO/SLA порог не задаётся, если явно не указано.

## 4. Инструменты и методика
- tool: k6
- Запуск: k6 с тремя сценариями (S1/S2/S3) через отдельные stages, с параметризацией base_url, auth, включением llm_latency_toggle для S3.
- Сбор метрик/отчётов:
  - k6 summary (stdout и JSON через `--summary-export`).
  - Теги: `test_scenario=S1|S2|S3`, `endpoint=<...>`.
  - Артефакты: сохраняем JSON-резюме и графики латентности/ошибок.
- Длительности по умолчанию (duration_defaults):
  - warmup: 2–3 мин
  - ramp: 2–5 мин
  - steady: 10–15 мин
- Время тайм-аута клиента: единообразно на уровне тестов (например, 30 с), чтобы корректно учитывать timeouts.

## 5. Сценарии

### 5.1. S1: Малый diff (<1K символов)
- Профиль: warmup 2 мин, ramp 2 мин до steady 8 RPS (диапазон 5–10 RPS), steady 10 мин.
- Инструмент: k6.
- Данные: data_shape_small.
- Длительность: warmup 2 мин / ramp 2 мин / steady 10 мин.
- Метрики: p95, p99, error rate, 5xx, timeouts.
- Критерии прохождения:
  - p95 < 500 мс.
  - error rate < 1%.
  - 5xx = 0%.
  - timeouts = 0%.
- Evidence:
  - k6 summary (пример):
    - http_reqs: 4800–5200
    - http_req_duration p(95): 430ms, p(99): 780ms
    - http_req_failed: 0.6%
    - 5xx: 0%, timeouts: 0%
  - Графики:
    - Латентность p95/p99 по времени.
    - RPS и error rate по времени.
  - Файлы:
    - artifacts/k6/S1/summary.json
    - artifacts/k6/S1/latency_p95_p99.png
    - artifacts/k6/S1/rps_errors.png

### 5.2. S2: Пограничный diff (~20 000 символов)
- Профиль: warmup 3 мин, ramp 3 мин до steady 3–4 RPS (диапазон 2–5 RPS), steady 12 мин.
- Инструмент: k6.
- Данные: data_shape_large.
- Длительность: warmup 3 мин / ramp 3 мин / steady 12 мин.
- Метрики: p95, p99, error rate, 5xx, timeouts.
- Критерии прохождения (REL-1):
  - p95 < 10 с (REL_1_ref: REL-1 — требование: p95 < 10 c для граничного diff).
  - timeouts < 1%.
  - error rate < 1%.
  - 5xx = 0%.
- Evidence:
  - k6 summary (пример):
    - http_reqs: 2400–3000
    - http_req_duration p(95): 8.5s, p(99): 11.4s
    - http_req_failed: 0.7%
    - 5xx: 0%, timeouts: 0.4%
  - Графики:
    - Латентность p95/p99 (подтверждение соответствия REL-1).
    - Стек ошибок/тайм-аутов.
  - Файлы:
    - artifacts/k6/S2/summary.json
    - artifacts/k6/S2/latency_p95_p99.png
    - artifacts/k6/S2/errors_timeouts.png

### 5.3. S3: Задержка LLM
- Профиль: warmup 2 мин, ramp 2 мин до steady 1–2 RPS, steady 10 мин.
- Инструмент: k6.
- Как включается задержка: llm_latency_toggle.
- Данные: data_shape_small.
- Длительность: warmup 2 мин / ramp 2 мин / steady 10 мин.
- Метрики: p95, p99, error rate, 5xx, timeouts (особый акцент).
- Критерии прохождения:
  - 5xx = 0%.
  - error rate < 1%.
  - timeouts — только ожидаемые из-за искусственной задержки, ≤ 1%; корректная деградация (нет обвалов RPS, нет неуправляемых очередей).
  - p95/p99 — фиксируются и прилагаются; без жёсткого порога в рамках этого сценария.
- Evidence:
  - k6 summary (пример):
    - http_reqs: 800–1200
    - http_req_duration p(95): 2.4s, p(99): 5.8s
    - http_req_failed: 0.5%
    - 5xx: 0%, timeouts: 0.8% (индуцированные)
  - Графики:
    - Распределение латентности при включённой задержке.
    - Тайм-ауты по времени.
  - Файлы:
    - artifacts/k6/S3/summary.json
    - artifacts/k6/S3/latency_with_llm_delay.png
    - artifacts/k6/S3/timeouts.png

## 6. План запуска и воспроизводимость
Переменные окружения:
- BASE_URL="<URL стенда/окружения>"
- AUTH="<Схема аутентификации/заголовки, если нужны>" (например, `Bearer <token>` или JSON заголовка)
- ENDPOINT="<Основной endpoint под нагрузкой>"
- LLM_TOGGLE="<Как включается/эмулируется задержка LLM: фича-флаг/заглушка/параметр>"
- HTTP_TIMEOUT_MS="30000" (пример)

Пример команд (k6):
- Каталог для артефактов:
  - mkdir -p artifacts/k6/S1 artifacts/k6/S2 artifacts/k6/S3
- S1:
  - k6 run --summary-export artifacts/k6/S1/summary.json -e BASE_URL="$BASE_URL" -e AUTH="$AUTH" -e ENDPOINT="$ENDPOINT" -e SCENARIO="S1" -e HTTP_TIMEOUT_MS="$HTTP_TIMEOUT_MS" --tag test_scenario=S1 scripts/k6/tests_load.js
- S2:
  - k6 run --summary-export artifacts/k6/S2/summary.json -e BASE_URL="$BASE_URL" -e AUTH="$AUTH" -e ENDPOINT="$ENDPOINT" -e SCENARIO="S2" -e HTTP_TIMEOUT_MS="$HTTP_TIMEOUT_MS" --tag test_scenario=S2 scripts/k6/tests_load.js
- S3:
  - k6 run --summary-export artifacts/k6/S3/summary.json -e BASE_URL="$BASE_URL" -e AUTH="$AUTH" -e ENDPOINT="$ENDPOINT" -e SCENARIO="S3" -e LLM_TOGGLE="$LLM_TOGGLE" -e HTTP_TIMEOUT_MS="$HTTP_TIMEOUT_MS" --tag test_scenario=S3 scripts/k6/tests_load.js

Примечания:
- Для генерации отчётных графиков используйте экспортированные summary.json и инструменты визуализации (например, Grafana/InfluxDB или off-line скрипты).
- Все артефакты складываются под artifacts/k6/<S#> и прикладываются к отчётам.

## 7. Привязка к требованиям и риски
- Соответствие REL_1_ref:
  - S2 напрямую валидирует REL-1: p95 < 10 с для граничного diff (~20 000 символов).
- Риски/долги:
  - monitoring: <Как собираются метрики ресурсов (CPU/RAM/GC), если доступно; иначе «n/a»>. Если n/a: TODO — интеграция системного мониторинга (например, прометей-экспортёр или k6 → InfluxDB → Grafana), согласование бюджетов CPU/RAM/GC, алертирование по деградациям.
  - Стабильность данных генераторов: TODO — зафиксировать генераторы входов для воспроизводимости (версии/seed).
  - Тайм-ауты прокси/балансировщиков: TODO — зафиксировать единые пороги на уровне инфраструктуры, чтобы исключить скрытые 504 от внешних компонентов.

## 8. Приложения (опционально)
- Шаблон команд:
  - k6 run --summary-export artifacts/k6/<SCENАРИО>/summary.json -e BASE_URL="$BASE_URL" -e AUTH="$AUTH" -e ENDPOINT="$ENDPOINT" -e SCENARIO="<S1|S2|S3>" scripts/k6/tests_load.js
- Ссылки на дашборды:
  - <Ссылка на Grafana/InfluxDB дашборд, если есть>
- Пример структуры отчётов:
  - artifacts/
    - k6/
      - S1/
        - summary.json
        - latency_p95_p99.png
        - rps_errors.png
      - S2/
        - summary.json
        - latency_p95_p99.png
        - errors_timeouts.png
      - S3/
        - summary.json
        - latency_with_llm_delay.png
        - timeouts.png
