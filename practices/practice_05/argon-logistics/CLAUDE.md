# Argon Logistics

C# (.NET 10) backend логистики и Next.js интерфейс в `web/`. Namespace `Argonum.Logistics.*`. Подробности: `README.md`, бизнес-логика: `docs/business-logic.md`.

## Правила проекта

- Весь backend на C#. Бизнес-логика планирования живёт в `Argonum.Logistics.Core` (без БД и HTTP) и покрывается unit-тестами.
- `web/` ничего не планирует сам: маршруты, резервы и статусы приходят из API. Фронт считает только геометрию (`web/src/lib/geometry.ts`, тесты vitest) и положение грузовика по `dispatchedAt`, `speedFactor` и серверному времени.
- Симуляция (`SimulationService`) выключена по умолчанию и включается `Simulation__Enabled`. Она отгружает и доставляет, выдачу делает человек. Тесты, не про симуляцию, её не включают.
- Стили: токены Material Design 3 в `web/src/app/globals.css`, без UI-библиотек; иконки и Roboto из npm.
- Любое изменение поведения идёт через OpenSpec: `/opsx:propose` → review → `/opsx:apply` → проверка → `/opsx:sync` и `/opsx:archive` (только после приёмки человеком).
- Поведение описывает spec (`openspec/changes/*/specs`, после архива `openspec/specs`); `docs/business-logic.md` его пересказывает. При расхождении прав spec, затем правим docs.
- Все операции, меняющие остатки или резервы, выполняются под `InventoryLock` и одним `SaveChanges`.
- Ошибки только через `DomainException(status, code, detail)`: код `snake_case`, формат `problem+json`.
- Уникальность без учёта регистра держим через `TextKey` (`*Key` колонки), не через коллацию SQLite: `NOCASE` не понимает кириллицу.
- Не используем OpenCode, только Claude Code.

## Команды

```bash
dotnet build
dotnet test
dotnet run --project src/Argonum.Logistics.Api --launch-profile http
openspec validate argon-logistics-core --type change --strict --no-interactive
openspec validate argon-web-console --type change --strict --no-interactive
cd web && npm test && npx tsc --noEmit && npm run build
docker compose up --build        # интерфейс :3000, API :5281
```
