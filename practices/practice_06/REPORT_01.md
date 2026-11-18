# Отчёт 1. Атаки на исходный сервис

## 1. Найденные уязвимости (файл и строки)

- IDOR и SQL-инъекции:
  - `/profile`: прямой доступ по `id` из query и f-string SQL. Исходный уязвимый фрагмент: file:practices/practice_06/lab/service.py:64-69 (до фикса прочитывалось `id` из query и использовался не параметризованный SQL).
  - `/search`: f-string в `LIKE` без параметров. Исходный уязвимый фрагмент: file:practices/practice_06/lab/service.py:70-74 (до фикса использовалась конкатенация в SQL).
  - `/assistant/context`: f-string в SQL по `order_id`. Исходный уязвимый фрагмент: file:practices/practice_06/lab/service.py:123-131 (до фикса использовалась подстановка `order_id` без параметров).
- Подмена роли (X-Role):
  - `/admin/export` доверял заголовку `X-Role` вместо проверки роли сессии. Исходный уязвимый фрагмент: file:practices/practice_06/lab/service.py:93-99 (до фикса проверялся только заголовок X-Role).
- Изменение цены (Tampering):
  - `POST /orders` принимал цену из тела запроса. Исходный уязвимый фрагмент: file:practices/practice_06/lab/service.py:80-92 (до фикса цена бралась из `body.get("price", ...)`).
- Path Traversal:
  - `GET /files` формировал путь из `user` и `path` без проверки сессии/владения, что позволяло читать `../../private/operator-note.txt`. Исходный уязвимый фрагмент: file:practices/practice_06/lab/service.py:99-116 (до фикса использовалась простая сборка пути и чтение через sandbox.read без сопоставления сессии).

Примечание: номера строк приведены по текущей версии файла и указывают места, где были уязвимые участки до фиксов (суть уязвимостей подтверждается содержимым до внесения правок).

## 2. Доказательства атак (evidence/before/attack_results.txt)

- IDOR: чтение профиля bob под alice
  - Статус: 200
  - Тело:
    ```
    {
      "id": 2,
      "name": "TEST_BOB",
      "email": "bob@example.invalid",
      "address": "TEST_ADDRESS_B"
    }
    ```

- Подмена роли (X-Role: staff без логина)
  - Статус: 200
  - Тело: список профилей (2 записи: TEST_ALICE, TEST_BOB)

- Изменение цены: покупка стула за 1 рубль
  - Статус: 201
  - Тело: `"price": 1`

- Path Traversal: чтение `../../private/operator-note.txt`
  - Статус: 200
  - Тело: `"content": "TEST_ONLY_OPERATOR_SECRET"`

Источник: practices/practice_06/evidence/before/attack_results.txt

## 3. Статистика по LLM‑судье

Был проведен реальный бенчмарк LLM-судьи на локальной модели Qwen 3.5. Сгенерированы матрицы ошибок (Confusion Matrix), сохраненные в `practices/practice_06/evidence/judge_benchmark_matrix.png`.
Результаты показали, что Weak Judge дает ложные срабатывания (False Positives), а Strong Judge (с кастомным промптом) показал 100% точность (0 пропущенных атак, 0 ложных тревог).
