# Spec Delta

## Purpose

HTTP-доступ к ревью диффа: HTML-страница и `POST /api/review`, которые
дают человеку вставить дифф в браузере и увидеть результат `review_diff`
(успех, отказ или ошибку модели) без написания кода.

## ADDED Requirements

### Requirement: HTML-страница ревью
Сервер SHALL отдавать по `GET /` HTML-страницу с текстовым полем для
диффа и кнопкой запуска ревью.

#### Scenario: Страница доступна
- **WHEN** клиент выполняет `GET /`
- **THEN** сервер возвращает HTTP 200 и HTML-документ, содержащий
  текстовое поле ввода диффа и кнопку запуска ревью

### Requirement: Успешный ответ ревью через API
`POST /api/review` с валидным диффом SHALL вызвать `review_diff` и
вернуть его результат как JSON с HTTP 200, когда `review_diff` возвращает
`status == "ok"`.

#### Scenario: Модель успешно отревьюировала дифф
- **WHEN** клиент отправляет `POST /api/review` с телом `{"diff":
  "<непустой дифф не длиннее MAX_DIFF_BYTES>"}`, и `review_diff`
  возвращает `{"status": "ok", "review": "<текст>", "stats": {...}}`
- **THEN** сервер отвечает HTTP 200 с телом, равным результату
  `review_diff`, без изменения полей

### Requirement: Отказ валидации входа через API
Когда `review_diff` возвращает `status == "rejected"`, `POST /api/review`
SHALL вернуть этот результат как JSON с HTTP 200: отказ — это
предусмотренный исход `review_diff`, а не ошибка HTTP-слоя.

#### Scenario: Пустой или слишком большой дифф
- **WHEN** клиент отправляет `POST /api/review` с диффом, который
  `review_diff` отклоняет (`empty_diff` или `diff_too_large`)
- **THEN** сервер отвечает HTTP 200 с телом `{"status": "rejected",
  "code": "<...>", "message": "<...>"}`, как вернул `review_diff`

### Requirement: Ошибка зависимости модели через API
Когда `review_diff` возвращает `status == "error"` (ошибка зависимости
модели), `POST /api/review` SHALL вернуть этот результат как JSON с
HTTP 200: ошибка зависимости — это предусмотренный исход `review_diff`,
а не отказ HTTP-слоя.

#### Scenario: Модель недоступна или ответила с ошибкой
- **WHEN** клиент отправляет `POST /api/review` с валидным диффом, и
  `review_diff` возвращает `{"status": "error", "code": "<model_*>",
  "message": "<...>", "stats": {...}}`
- **THEN** сервер отвечает HTTP 200 с телом, равным результату
  `review_diff`, без изменения полей

### Requirement: Отказ при некорректном HTTP-запросе
`POST /api/review` с телом, которое не является JSON-объектом с ключом
`diff` (типа `str`), SHALL быть отклонён HTTP-слоем до вызова
`review_diff`, c кодом ответа HTTP 400 и телом, описывающим причину.

#### Scenario: Тело запроса не JSON
- **WHEN** клиент отправляет `POST /api/review` с телом, которое не
  парсится как JSON
- **THEN** сервер отвечает HTTP 400 и не вызывает `review_diff`

#### Scenario: Отсутствует или некорректен ключ diff
- **WHEN** клиент отправляет `POST /api/review` с JSON-телом без ключа
  `diff` или со значением `diff`, не являющимся строкой
- **THEN** сервер отвечает HTTP 400 и не вызывает `review_diff`

### Requirement: Отказ при неподдерживаемом маршруте
Запрос к любому пути или методу, кроме `GET /` и `POST /api/review`,
SHALL получать HTTP 404 без вызова `review_diff`.

#### Scenario: Неизвестный путь
- **WHEN** клиент выполняет запрос к пути, отличному от `/` и
  `/api/review`
- **THEN** сервер отвечает HTTP 404 и не вызывает `review_diff`
