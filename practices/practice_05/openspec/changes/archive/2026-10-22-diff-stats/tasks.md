# Tasks

## 1. Подсчёт статистики и подключение к успешному ответу

- [x] 1.1 В `app/review.py` добавить приватную функцию подсчёта статистики
      диффа по правилу "Правило подсчёта статистики" из
      `specs/review-diff/spec.md` (пара `--- X`/`+++ Y` — заголовок файла;
      одиночная `--- X` без следующей `+++ Y` и одиночная `+++ Y` без
      предшествующей `--- X` считаются как `removed`/`added`
      соответственно; диффы без распознаваемых конструкций дают
      `{"files": 0, "added": 0, "removed": 0}`) и проверить через
      `python3 -m compileall -q app`.
- [x] 1.2 Подключить подсчёт к ветке `{"status": "ok", ...}`: добавить ключ
      `"stats"` к возвращаемому словарю и проверить через новый тест
      `test_returns_stats_for_successful_review` в `tests/test_review.py`
      (вызов `review_diff` с диффом, содержащим пару `---`/`+++` и строки
      `+`/`-`, проверка точных значений `files`/`added`/`removed`).
- [x] 1.2a Обновить существующий тест `test_returns_model_answer`
      (`tests/test_review.py:131-134`): добавить ожидаемый `stats` в
      литерал словаря, с которым сравнивается результат
      (`"--- a\n+++ b\n+print(1)\n"` даёт `{"files": 1, "added": 1,
      "removed": 0}`), и проверить `sh scripts/check.sh`. Других мест в
      `tests/test_review.py`, где результат `ok`/`error`-ответа сравнивается
      целиком через `assertEqual(result, {...})`, нет (проверено поиском по
      `assertEqual(result,`), так что других тестов менять не требуется.
- [x] 1.3 Добавить тест на правило "`--- x` без следующей `+++`": дифф со
      строкой `--- x`, представляющей удалённую исходную строку `-- x`,
      после которой следующая строка не начинается с `+++ `, — и проверить,
      что эта строка учтена в `removed`, а `files` не увеличился: тест
      `test_removed_line_without_file_header_is_not_counted_as_file` в
      `tests/test_review.py`.
- [x] 1.3a Добавить тест на одиночную строку `+++ y` без предшествующей
      `--- X`: проверить, что она учтена в `added`, а `files` не
      увеличился: тест
      `test_standalone_plus_plus_plus_line_is_counted_as_added` в
      `tests/test_review.py`.
- [x] 1.4 Добавить тест на дифф без распознаваемых конструкций (например,
      только текст без `+`/`-`/`---`/`+++`) и проверить, что `stats` равен
      `{"files": 0, "added": 0, "removed": 0}`: тест
      `test_returns_zero_stats_when_diff_has_no_recognizable_markers` в
      `tests/test_review.py`.

## 2. Статистика в ответах об ошибке зависимости

- [x] 2.1 Подключить тот же подсчёт к каждой ветке
      `{"status": "error", "code": "model_*", ...}` в `app/review.py` и
      проверить через новый тест
      `test_returns_stats_when_model_times_out` в `tests/test_review.py`
      (используя существующий `TimeoutClient`, проверить наличие и значения
      `stats` в ответе).
- [x] 2.2 Добавить аналогичный тест для `model_unavailable`:
      `test_returns_stats_when_model_unavailable` в `tests/test_review.py`
      (используя существующий `UnavailableClient`).
- [x] 2.3 Добавить аналогичный тест для `model_http_error`:
      `test_returns_stats_when_model_http_error` в `tests/test_review.py`
      (используя существующий `HttpErrorClient`).
- [x] 2.4 Добавить аналогичный тест для `model_bad_response`:
      `test_returns_stats_when_model_bad_response` в `tests/test_review.py`
      (используя существующий `BadResponseClient`).
- [x] 2.5 Добавить тест stats для ветки `except http.client.HTTPException`
      (код `model_bad_response`), используя существующий
      `RemoteDisconnectedClient`: тест
      `test_returns_stats_when_remote_disconnects_without_response` в
      `tests/test_review.py`. Эта ветка не покрыта существующими тестами
      2.1-2.4 (те используют другие клиенты), и без неё удаление `stats`
      из `except http.client.HTTPException` (`app/review.py:97-103`) не
      ловится проверкой.
- [x] 2.6 Добавить тест stats для ветки `except OSError`
      (код `model_unavailable`), используя существующий
      `TransportErrorClient`: тест
      `test_returns_stats_when_transport_error_occurs` в
      `tests/test_review.py`. Без него удаление `stats` из `except OSError`
      (`app/review.py:104-110`) не ловится проверкой.

## 3. Регрессия: rejected-ответы без stats

- [x] 3.1 Добавить тесты, подтверждающие, что ключ `"stats"` отсутствует в
      ответах `{"status": "rejected", ...}`: тесты
      `test_rejected_empty_diff_has_no_stats_key` и
      `test_rejected_oversized_diff_has_no_stats_key` в
      `tests/test_review.py`, проверяющие `"stats" not in result`.

## 4. Документация контракта

- [x] 4.1 Обновить `docs/requirements.md`: описать поле `"stats":
      {"files": N, "added": N, "removed": N}` в разделе успеха и в разделе
      фичи B (ошибка зависимости), явно указать правило распознавания
      заголовка файла и случай `--- x` без `+++`, а также то, что поле
      отсутствует в `rejected`-ответах. Проверить, что текст не меняет
      существующие таблицы кодов и сигнатуру `review_diff`.

## 5. Финальная проверка

- [x] 5.1 Запустить `sh scripts/check.sh` из `practices/practice_05` и
      убедиться, что компиляция и все тесты (старые и новые) проходят
      зелёным.

## Workflow follow-up

- Показать итоговый вывод `sh scripts/check.sh` и отчитаться по
  `файл:строка` для каждого утверждения, как требует `AGENTS.md`.
- Архивировать change после приёмки результата.
