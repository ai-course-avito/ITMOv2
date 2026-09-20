# R.C.T.F.

- **Role:** QA-инженер/разработчик, проверяющий метрики для стабильности эндпоинта `/api/reviews`.
- **Context:** план локального/CI стенда; «малый diff» ≤ 10 KB; мок LLM с фиксированной задержкой 100 ms; 100 последовательных запросов; фактические замеры ещё не собраны.
- **Task:** сформировать воспроизводимый протокол проверки метрик и шаблон отчёта, не подставляя вымышленные результаты.
- **Format:** JSON с `expected_result`, `actual_result`, `evidence_status` и `evidence`.

## Полный запрос

Сконструируй R.C.T.F. промпт для уточнения и проверки метрик файла `practices/practice_01/problem.md`:

- Role: QA-инженер/разработчик.
- Context: планируемый стенд, «малый diff» ≤ 10 KB, мок LLM 100 ms, 100 запросов; evidence ещё не собрано.
- Task: описать протокол для HTTP 422, HTTP 502 с `LLM_UPSTREAM_ERROR`, границ 19 999/20 000/20 001 и сравнения P95 с baseline.
- Format: вернуть шаблон отчёта с ожидаемыми значениями, `actual_result=null` и `evidence_status=not_collected`, а также шаги запуска.

## Что получили

Шаблон отчёта до фактического запуска:

```json
{
  "timestamp": null,
  "env": "planned",
  "inputs": {
    "llm_mock_latency_ms": 100,
    "requests": 100,
    "small_diff_max_kb": 10
  },
  "expected_result": {
    "empty_or_missing_diff_status": 422,
    "llm_error_status": 502,
    "llm_error_code": "LLM_UPSTREAM_ERROR",
    "diff_limit_characters": 20000,
    "boundary": {
      "19999": "accepted",
      "20000": "accepted",
      "20001": 413
    },
    "p95_rule": "p95_after <= p95_baseline"
  },
  "actual_result": null,
  "evidence_status": "not_collected",
  "evidence": []
}
```

Шаги проверки после появления реализованного сервиса:

1. Отправить `{}` и `{"diff":"   "}`; ожидать 422 и отсутствие вызова LLM.
2. Настроить мок LLM на исключение и timeout больше 10 секунд; ожидать 502 и `LLM_UPSTREAM_ERROR`.
3. Передать Unicode-строки длиной 19 999, 20 000 и 20 001 символ после JSON decode и до redaction; ожидать accept, accept, 413.
4. Выполнить baseline и повторный замер по 100 запросов в одинаковых условиях; проверить `P95_after <= P95_baseline`.

Критерий принятия: после запуска `actual_result` совпадает с `expected_result`, а `evidence` содержит реальные идентификаторы тестов или отчётов. До запуска сохраняются `actual_result=null` и `evidence_status=not_collected`.

## Что изменили в исходном артефакте

- Файл и раздел: `practices/practice_01/problem.md`, разделы «Метрики» и «Почему изменение метрики подтвердит решение проблемы».
- Изменение: добавили Role, Context, Task, Format; удалили вымышленные результаты и пути; отделили expected от actual.
- Как проверили: JSON-шаблон не утверждает факт запуска; каждый критерий связан с конкретным тестовым входом.
- Что отклонили: расплывчатые формулировки без условий стенда и без формата отчётности.
