# Few-shot

- Артефакт Практики 1: `practices/practice_01/product_management.md` — раздел «User Stories и acceptance criteria»
- Что хотим улучшить: переписать свободный текст критериев приёмки в воспроизводимые Gherkin-сценарии

## Примеры

### Хороший результат

```gherkin
Scenario: 422 when diff is missing
  Given тело без поля "diff"
  When отправляем POST "/api/reviews"
  Then получаем 422 с описанием отсутствующего поля
```

### Плохой результат

Свободный текст: «Если diff не пришёл, нужно показать ошибку и не падать».

## Запрос

Сконвертируй acceptance criteria для US-01..US-05 из свободного текста в Gherkin. Используй Given/When/Then, на русском, минимизируй риторику. Выравни с правилами CASE.md (SEC-1, API-1, REL-1, OUT-1) и метриками из problem.md.

## Что получили

- Для US-01..US-05 сформированы по 2–3 сценария каждый в блоках ```gherkin```, согласованные с CASE.md.

## Что изменили в исходном артефакте

- Файл и раздел: `practices/practice_01/product_management.md` — «User Stories и acceptance criteria»
- Изменение: добавлены блоки ```gherkin``` для каждой US; уточнена формулировка US-02 (см. Chain of Verification)
- Как проверили: `make -C practices/practice_01 test` (поиск ```gherkin); соответствие метрикам `problem.md`
- Что отклонили: любые критерии без Given/When/Then и без привязки к CASE.md
