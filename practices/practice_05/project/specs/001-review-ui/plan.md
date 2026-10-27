# Implementation Plan: Браузерное ревью diff — UI

**Branch**: `practice_05` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-review-ui/spec.md`; [CONTRACT v1.0](../../../CONTRACT.md), одобренный пользователем.

## Summary

Один экран вставки diff и чтения рекомендации. Статический HTML/CSS и vanilla JavaScript без сборки, отдаваемые FastAPI с тем же origin. UI проверяет границы, безопасно показывает результат и режим, управляет loading/error и игнорирует поздние ответы. Backend, провайдер и полная проверка evidence — зона команды логики; интеграция и Playwright — координатора. Этот этап создаёт только плановые документы.

## Technical Context

**Language/Version**: HTML5, CSS, browser JavaScript ES2020+ (без transpiler).

**Primary Dependencies**: браузерные DOM, Fetch, AbortController; runtime npm-зависимостей нет. FastAPI предоставляет GET /, /static/* и POST /api/reviews, его версию закрепляет команда логики.

**Storage**: только текущий DOM и память попытки; без URL-параметров, cookies, localStorage, истории и журналирования содержимого.

**Testing**: сквозные Playwright-проверки у координатора, управление ответами через test routes для отказов/late response; ручная клавиатура, screen reader, адаптивность. Тесты не доказывают качество live-модели.

**Target Platform**: современный браузер с Fetch/AbortController; контрольный автоматизированный браузер Chromium; ширины от 360 CSS px, масштаб 200%.

**Project Type**: локальное web-приложение, статический клиент и API одного origin.

**Performance Goals**: один активный запрос; loading прекращается в пределах 15 секунд; UI не блокирует ввод долгой локальной обработкой. Внешний анализ ограничен 10 секундами на сервере.

**Constraints**: 20000 Unicode code points; literal rendering; до трёх возможных рисков; checks непустой; секрет провайдера вне клиента; «ДЕМО» для demo; никакого approve/merge.

**Scale/Scope**: один экран и один diff; без авторизации, истории, сборщика или внешней публикации.

## Constitution Check

| Принцип | До Phase 0 | После Phase 1 |
| --- | --- | --- |
| Две независимые specs и один контракт | PASS: drafts сохранены, общий контракт принят | PASS: данные и UI соответствуют v1.0 |
| Решение человека до кода | PASS: evidence/approval.md, код ещё не написан | PASS: только документы; реализация после снимков «после» координатором |
| Проверяемые рекомендации | PASS: поля и цитаты заданы | PASS: UI не выдаёт цитату за истинность риска, сервер проверяет координаты |
| Минимизация раскрытия | PASS: ключ только backend, нет истории | PASS: literal text, без storage/log тела, маскирование у backend |
| Наблюдаемая приёмка | PASS: успех и ошибка обязательны | PASS: quickstart и задачи охватывают совместный запуск; результаты пока не заявлены |

Нарушений или исключений нет. Неопределённостей, блокирующих UI, после согласования нет. Дополнительные исследовательские агенты для разрешения неизвестных не нужны: стек и границы заданы координатором и контрактом; локальные решения описаны в research.md.

## Project Structure

### Documentation (this feature)

```text
specs/001-review-ui/
├── spec.md
├── contract-proposal.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/ui-interface.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
static/
├── index.html   # форма, подписи, состояния, секции результата
├── app.js       # валидация, lifecycle запроса, literal rendering
└── styles.css   # адаптивность, фокус, контраст
```

**Structure Decision**: три статических файла без npm/build; backend размещает их на том же origin. Команда UI не изменяет backend или e2e-тесты координатора. Проектирование DOM contract позволяет проверять страницу через роли и доступные названия.

## Complexity Tracking

Нарушений constitution нет; дополнительные проекты, библиотеки состояния и слои хранения не вводятся.

## Workflow evidence

setup-plan.sh выполнен с SPECIFY_INIT_DIR, SPECIFY_FEATURE_DIRECTORY=specs/001-review-ui, SPECIFY_FEATURE_NO_PERSIST=1 и SPECIFY_FEATURE=practice_05. Шаблон разрешён установленным resolver и скопирован в этот plan.md. Shared feature.json не изменялся. `.specify/extensions.yml` отсутствует: pre/post hooks не требуются.
