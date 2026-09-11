# Нагрузочные проверки

## 1. Для чего

Цель документа — описать практический план нагрузочного тестирования для
сервиса AI-ревью PR (`POST /api/reviews` → `ReviewService.review` → внешний LLM).
Нагружаем основной endpoint для малых и пограничных диффов, а также проверяем
поведение при включённой задержке LLM.

Успех определяется соответствием измеренных метрик целевым SLO/SLA:
- p95 < 500 мс для малого diff и < 10 с для пограничного diff (REL-1);
- error rate < 1%;
- 5xx = 0%;
- контролируемые timeouts в S3 (0% 500).

Evidence — только результаты замеров (k6 summary/Locust отчёты/графики).

## 2. Область и система под тестом

- product_name: AI-ассистент ревью кода (FastAPI-сервис)
- endpoint_under_test: `POST /api/reviews`
- base_url: `<URL стенда/окружения>`
- auth: не требуется (учебный сервис)
- llm_latency_toggle: feature flag `LLM_DELAY=<секунды>` (эмулирует задержку LLM)
- data_shape_small: diff <1 000 символов, типичные изменения (1–5 строк)
- data_shape_large: diff ~20 000 символов (граница API-1)
- monitoring: n/a (TODO — интеграция k6 → InfluxDB → Grafana для CPU/RAM/GC)

Ограничения:
- Тестируем только `POST /api/reviews`. Внешние LLM-провайдеры мокаются через
  feature flag.
- Сеть и балансировщики рассматриваются как «as is».

## 3. Метрики и цели (SLO/SLA)

Определения:
- **p95/p99** — 95-й/99-й перцентиль времени ответа HTTP-запроса.
- **error rate** — доля запросов с ошибкой (HTTP 4xx/5xx + сетевые ошибки), %.
- **5xx** — доля ответов с HTTP-статусом 5xx, %.
- **timeouts** — доля запросов, завершившихся таймаутом (408/504 или client-side
  timeout), %.
- **request_id tracking** — логируемые поля: request_id, duration, status (OBS-1).

| Сценарий | Целевая нагрузка | p95 (SLO) | error rate (SLO) | 5xx (SLO) | timeouts (SLO) | SLA |
|---|---|---|---|---|---|---|
| S1: Малый diff (<1K) | 5–10 RPS (steady 8) | < 500 мс | < 1% | 0% | 0% | TBD |
| S2: Пограничный diff (~20K) | 2–5 RPS (steady 3–4) | < 10 с (REL-1) | < 1% | 0% | < 1% | TBD |
| S3: Задержка LLM | 1–2 RPS | — | < 1% | 0% | ≤ 1% (контролируемые) | TBD |

> p99 во всех сценариях фиксируется и прикладывается в evidence, но порог SLO
> для p99 не задаётся, если явно не указано. SLA-значения помечены TBD до
> получения продакшен-данных.

## 4. Инструменты и методика

- **Инструмент:** k6 (для S1 и S2), Locust (для S3 — удобнее управлять задержками).
- **Профиль нагрузки:** warmup → ramp → steady для каждого сценария.
- **Длительности по умолчанию:** warmup 2–3 мин, ramp 2–5 мин, steady 10–15 мин.
- **Сбор метрик:**
  - k6 summary (stdout + JSON через `--summary-export`).
  - Locust stats (CSV/скриншоты веб UI).
  - Теги: `test_scenario=S1|S2|S3`.
- **Artifact paths:** `artifacts/<instrument>/<S#>/summary.json`, графики.

## 5. Сценарии

### 5.1. S1 — Малый diff (<1 000 символов)

- **Инструмент:** k6
- **Данные:** `data_shape_small` (diff <1K)
- **Профиль:** warmup 2 мин @ 5 RPS → ramp 2 мин до steady 8 RPS → steady 10 мин
- **Метрики:** p95, p99, error rate, 5xx, timeouts
- **Критерии pass/fail:**
  - p95 < 500 мс
  - error rate < 1%
  - 5xx = 0%
  - timeouts = 0%
- **Evidence:** k6 summary с p95/p99/http_req_failed; график latency p95/p99.
  - *Пример (ожидается после прогона):*
    - http_reqs: ~4800
    - http_req_duration p(95): 430ms, p(99): 780ms
    - http_req_failed: 0.6%
    - 5xx: 0, timeouts: 0
  - Файлы: `artifacts/k6/S1/summary.json`, `artifacts/k6/S1/latency_p95_p99.png`

```bash
k6 run --summary-export artifacts/k6/S1/summary.json \
  -e BASE_URL="$BASE_URL" -e ENDPOINT="$ENDPOINT" -e SCENARIO="S1" \
  scripts/k6/tests_load.js
```

### 5.2. S2 — Пограничный diff (~20 000 символов)

- **Инструмент:** k6
- **Данные:** `data_shape_large` (diff ~20K)
- **Профиль:** warmup 3 мин @ 2 RPS → ramp 3 мин до steady 3–4 RPS → steady 12 мин
- **Метрики:** p95, p99, error rate, 5xx, timeouts
- **Критерии pass/fail (REL-1):**
  - p95 < 10 с
  - timeouts < 1%
  - error rate < 1%
  - 5xx = 0%
  - diff > 20 000 символов → HTTP 413 (API-1) — проверяется отдельной проверкой
- **Evidence:** k6 summary с p95 и долей таймаутов; график errors/5xx.
  - *Пример (ожидается после прогона):*
    - http_reqs: ~2600
    - http_req_duration p(95): 8.5s, p(99): 11.4s
    - http_req_failed: 0.7%
    - 5xx: 0, timeouts: 0.4%
  - Файлы: `artifacts/k6/S2/summary.json`, `artifacts/k6/S2/errors_timeouts.png`

```bash
k6 run --summary-export artifacts/k6/S2/summary.json \
  -e BASE_URL="$BASE_URL" -e ENDPOINT="$ENDPOINT" -e SCENARIO="S2" \
  scripts/k6/tests_load.js
```

### 5.3. S3 — Задержка LLM (индуцированная)

- **Инструмент:** Locust
- **Данные:** `data_shape_small` + включение `llm_latency_toggle`
- **Профиль:** warmup 2 мин @ 1 RPS → ramp 2 мин до steady 2 RPS → steady 10 мин
- **Инъекция задержек:** feature flag `LLM_DELAY=12` (LLM отвечает через 12 с,
  что превышает REL-1 timeout 10 с)
- **Метрики:** p95, p99, error rate, 5xx, timeouts (особый акцент)
- **Критерии pass/fail:**
  - 5xx = 0% (таймауты обрабатываются контролируемо, без 500)
  - error rate < 1%
  - timeouts ≤ 1% и только из-за искусственной задержки
  - отсутствие неуправляемых очередей и обвалов RPS на steady
- **Evidence:** Locust stats CSV + скриншот веб UI; лог статусов (200/timeout-handled).
  - *Пример (ожидается после прогона):*
    - requests: ~1200
    - response_time p95: 2.4s, p99: 5.8s
    - failures: 0.5%
    - 5xx: 0%, timeouts: 0.8% (индуцированные)
  - Файлы: `artifacts/locust/S3/stats.csv`, `artifacts/locust/S3/web_ui.png`

```bash
LLM_DELAY=12 locust -f scripts/locust/tests_load.py --headless \
  --run-time 15m -u 2 -r 1 --csv artifacts/locust/S3/stats
```

## 6. Порог включения нагрузки

Нагрузочное тестирование включается при реальном трафике **> 10 запросов/минуту**
либо при регулярных REL-1 таймаутах в продакшене. До появления продакшен-данных
используем учебный diff и три сценария выше для валидации поведения.

## 7. Риски и TODO

- **p99, SLA, пороги 5xx** — TBD до получения первых замеров. После прогона
  зафиксировать значения и обновить SLO/SLA.
- **monitoring** — CPU/RAM/GC не собираются. TODO: интеграция k6 → InfluxDB →
  Grafana, согласование бюджетов ресурсов.
- **S3** — способ инъекции задержек (feature flag vs mock LLM) уточнять у команды.
- **Evidence** — пока плейсхолдеры. Требуется приложить реальные k6 summary и
  Locust отчёты в CI (см. план запуска).

## Как использовали AI

- Для чего: выбор стратегии нагрузочного тестирования из трёх альтернатив
  (Tree of Thoughts — A/B/C) и построение сценарного плана на их основе.
- Тип промпта: Tree of Thoughts (перебор альтернатив с оценкой по критериям).
- Строка в [`prompts.md`](prompts.md) таблицы Практики 2: `Tree of Thoughts`.
- Что проверили сами: наличие трёх сценариев с профилями/метриками/pass/fail;
  порог включения нагрузки; соответствие API-1 (413) и REL-1 (timeout 10 с);
  отсутствие ссылок на `len(diff)` в evidence; пометка TBD там, где нет замеров.

## 8. Открытые вопросы

- SLA значения (p99 пороги, допуск в 5xx) — TBD до появления prod-данных.
- Способ инъекции задержек LLM (feature flag vs mock) — уточнить у команды.
- Интеграция системного мониторинга (CPU/RAM/GC) — план в рисках/TODO.
