# Spec Delta

## Purpose

Запуск всей системы (API и веб-интерфейс) одной командой Docker Compose, с сохранением данных между перезапусками.

## ADDED Requirements

### Requirement: Запуск одной командой
Команда `docker compose up --build` в корне проекта SHALL собирать и запускать два сервиса, `api` и `web`, без ручной настройки. Веб-интерфейс SHALL быть доступен на порту 3000 хоста.

#### Scenario: Чистый запуск
- **WHEN** на чистой машине с Docker выполняется `docker compose up --build`
- **THEN** через некоторое время `http://localhost:3000` отдаёт интерфейс

### Requirement: Проксирование API
Веб-сервис SHALL проксировать запросы `/api/*` на сервис `api` внутри сети Compose, так что браузеру достаточно одного origin и CORS не нужен. Адрес API SHALL задаваться переменной окружения и читаться в рантайме.

#### Scenario: Запрос через web
- **WHEN** браузер вызывает `GET http://localhost:3000/api/network`
- **THEN** ответ тот же, что у `GET /api/network` самого API

#### Scenario: Заголовок пользователя проходит
- **WHEN** запрос `/api/me/orders` приходит с `X-User-Id`
- **THEN** API получает этот заголовок и отвечает от имени пользователя

### Requirement: Сохранность данных
База SHALL храниться в именованном volume, поэтому данные переживают `docker compose down` и повторный `up`. Симуляция логистики в Compose SHALL быть включена.

#### Scenario: Перезапуск
- **WHEN** выполнены `docker compose down` и `docker compose up`
- **THEN** склады, ПВЗ, связи и заказы на месте

### Requirement: Готовность сервисов
Сервис `api` SHALL иметь healthcheck, а `web` SHALL стартовать после того, как `api` здоров.

#### Scenario: Порядок старта
- **WHEN** `api` ещё не здоров
- **THEN** `web` не запускается, пока healthcheck не пройден
