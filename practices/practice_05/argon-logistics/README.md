# Argon Logistics

Логистика на C# (.NET 10, ASP.NET Core minimal API, EF Core + SQLite) с веб-интерфейсом на Next.js. Namespace `Argonum.Logistics`.
Склады, ПВЗ и общий каталог; граф путей между складами со временем; планирование доставки; заказы клиента;
карта-редактор, планшет заказа и живые грузовики.

Бизнес-логика: [docs/business-logic.md](docs/business-logic.md). Спецификации (OpenSpec): `openspec/changes/argon-logistics-core/` (backend)
`openspec/changes/argon-web-console/` (карта, симуляция, интерфейс, docker) и `openspec/changes/argon-returns/` (вместимость складов, отказ от товара).

## Запуск всего в Docker

```bash
docker compose up --build
```

- Интерфейс: http://localhost:3000 (запросы `/api/*` проксируются на API внутри сети compose).
- API напрямую: http://localhost:5281 (только с этого компьютера).
- Данные лежат в томе `argon-data` и переживают `docker compose down`; `docker compose down -v` стирает их.
- На пустой карте кнопка «Загрузить демо-сеть» создаёт 3 склада, 2 ПВЗ, пути и товары.
- В compose включена симуляция: 1 секунда = 3 минуты пути, отгрузка через 6 секунд после заказа, доставка сама,
  выдачу («Получить») делает человек. Настройки: `Simulation__Enabled`, `Simulation__SpeedFactor`,
  `Simulation__DispatchDelaySeconds`, `Simulation__TickMilliseconds`. Без симуляции (по умолчанию при `dotnet run`)
  отгрузку и доставку нажимают вручную в карточке заказа.
- Схема БД менялась (колонки `MapX`/`MapY`, `Capacity`, таблицы возвратов); старый `argon.db` и том `argon-data` несовместимы,
  их нужно удалить: `docker compose down -v` (миграций нет, используется `EnsureCreated`).

## Запуск без Docker

```bash
dotnet run --project src/Argonum.Logistics.Api --launch-profile http
```

Приложение слушает `http://localhost:5281`, база создаётся в `argon.db` рядом с рабочей папкой.
Свой файл БД: `ConnectionStrings__Argon="Data Source=/path/argon.db"`.
В `Development` схема OpenAPI доступна на `/openapi/v1.json`.
Готовые запросы: [requests.http](requests.http) (VS Code REST Client / Rider).

Веб-интерфейс отдельно (нужен запущенный API; `API_URL` по умолчанию `http://localhost:5281`):

```bash
cd web && npm install && npm run dev   # http://localhost:3000
```

## Тесты

```bash
dotnet test                     # backend
cd web && npm test              # математика карты и грузовиков (vitest)
cd web && npx tsc --noEmit      # типы
```

150 backend-тестов: unit для `DeliveryPlanner` и интеграционные через `WebApplicationFactory` (у каждого теста свой SQLite-файл,
в том числе карта, `/api/network` и симуляция) и 17 тестов vitest. Браузерных e2e-тестов в репозитории нет: интерфейс
проверялся вручную сценариями Playwright вне репозитория.

## Структура

```
src/Argonum.Logistics.Core   сущности и DeliveryPlanner (чистая логика, без БД и HTTP)
src/Argonum.Logistics.Api    EF Core, сервисы, endpoints, SimulationService
tests/Argonum.Logistics.Tests
web/                         Next.js 16: карта-редактор, каталог, планшет заказа, грузовики
docker-compose.yml           api + web, том с базой
openspec/                    SDD: proposal, specs, design, tasks
docs/business-logic.md       бизнес-логика
```

## API

| Область | Эндпоинты |
|---|---|
| Каталог | `GET/POST /api/products`, `GET/PUT/DELETE /api/products/{id}` |
| Склады | `GET/POST /api/warehouses`, `GET/PUT/DELETE /api/warehouses/{id}` |
| Остатки | `GET/POST /api/warehouses/{id}/stock`, `PUT/DELETE /api/warehouses/{id}/stock/{productId}` |
| ПВЗ | `GET/POST /api/pickup-points`, `GET/PUT/DELETE /api/pickup-points/{id}` |
| Привязки ПВЗ | `GET /api/pickup-points/{id}/links`, `PUT/DELETE /api/pickup-points/{id}/links/{warehouseId}` |
| Пути между складами | `GET/POST /api/routes`, `GET/PUT/DELETE /api/routes/{id}` |
| Планирование (dry-run) | `POST /api/plans` |
| Пользователи | `POST /api/users`, `GET /api/users/{id}` |
| Заказы клиента (`X-User-Id`) | `POST/GET /api/me/orders`, `GET /api/me/orders/{id}`, `POST /api/me/orders/{id}/cancel` |
| Отказ от товара (`X-User-Id`) | `POST /api/me/orders/{id}/returns` (только заказ в статусе `ReadyForPickup`) |
| Возвраты (dry-run, оператор) | `POST /api/return-plans`, `POST /api/returns/{id}/dispatch`, `POST /api/returns/{id}/deliver` |
| Оператор | `GET /api/orders`, `GET /api/orders/{id}`, `POST /api/orders/{id}/pickup`, `POST /api/shipments/{id}/dispatch`, `POST /api/shipments/{id}/deliver` |
| Карта | `PUT /api/warehouses/{id}/position`, `PUT /api/pickup-points/{id}/position`, `GET /api/network` (склады с суммами остатков, ПВЗ, пути, привязки) |
| Симуляция | `GET /api/simulation` (`enabled`, `speedFactor`, `dispatchDelaySeconds`, `serverTime`) |

## Быстрый пример

```bash
B=http://localhost:5281; H='Content-Type: application/json'
curl -X POST $B/api/products   -H "$H" -d '{"sku":"MILK","name":"Milk"}'
curl -X POST $B/api/warehouses -H "$H" -d '{"name":"North","address":"Moscow"}'
curl -X POST $B/api/pickup-points -H "$H" -d '{"name":"Arbat","address":"Moscow"}'
curl -X POST $B/api/warehouses/1/stock -H "$H" -d '{"productId":1,"quantity":10}'
curl -X PUT  $B/api/pickup-points/1/links/1 -H "$H" -d '{"minutes":30}'
curl -X POST $B/api/users -H "$H" -d '{"name":"Ivan","email":"ivan@example.com"}'
curl -X POST $B/api/plans -H "$H" -d '{"pickupPointId":1,"items":[{"productId":1,"quantity":3}]}'
curl -X POST $B/api/me/orders -H "$H" -H 'X-User-Id: 1' -d '{"pickupPointId":1,"items":[{"productId":1,"quantity":3}]}'
```

На Windows (Git Bash) кириллицу в `-d` curl может испортить; шлите тело из UTF-8 файла: `--data-binary @body.json`.

## OpenSpec

Инструмент поставлен глобально (`@fission-ai/openspec@1.14.1`), клиент: Claude Code (`/opsx:*`, skills в `.claude/`).

```bash
openspec list
openspec validate argon-logistics-core --type change --strict --no-interactive
openspec validate argon-web-console --type change --strict --no-interactive
openspec validate argon-returns --type change --strict --no-interactive
```

Все change (`argon-logistics-core`, `argon-web-console`, `argon-returns`) реализованы, но ещё не заархивированы: архив (`/opsx:sync`, `/opsx:archive`) только после приёмки.
