# Tasks: Браузерное ревью diff — UI

**Input**: Design documents from `specs/001-review-ui/`  
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/ui-interface.md; CONTRACT v1.0 одобрен. Координатор сохраняет итоговые specs до начала кода.  
**Tests**: smoke/e2e создаёт и выполняет координатор в tests/test_e2e.py; UI предоставляет точки интеграции и исправляет найденное. Здесь только 10 UI-задач, без дублирующей инфраструктуры тестов.  
**Organization**: задачи сгруппированы по US1–US3; выполнение отмечается по фактической реализации.

## Format: `[ID] [P?] [Story] Description`

`[P]` допускает независимую работу в другом файле. Пути ниже относительны project; изменять backend и tests/test_e2e.py команда UI не должна.

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Создать static/index.html: одну русскоязычную форму с именами из contracts/ui-interface.md, textarea без maxlength, счётчик, обе кнопки, status/error и скрытые секции результата; подключить /static/app.js и /static/styles.css, никаких ключей или переключателя режима.

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T002 Создать static/app.js с единой моделью ViewState «ровно idle, loading, success, error», DOM-ссылками и локальным Attempt; один loading одновременно, без URL/storage/log содержимого, управление disabled и очисткой result/error централизовано.

**Checkpoint**: форма и состояния готовы к независимой проверке управляемыми исходами.

## Phase 3: User Story 1 - Получить проверяемую рекомендацию (Priority: P1) 🎯 MVP

**Goal**: показать корректный результат и режим модели.  
**Independent Test**: учебный diff через работающий API/demo даёт три секции; управляемые 0/3 риска и literal markup отображаются корректно.

- [X] T003 [US1] В static/app.js проверять ответ целиком: request_id «непустая строка», mode «только live или demo», summary «1–1500 code points, непустая после trim», risks «массив 0–3 Risk», checks «массив 1–10 строк, каждая 1–500 code points и непустая после trim»; у Risk «ровно четыре поля: file, line, evidence, risk», file «непустая строка», line «целое число > 0, boolean запрещён», evidence «1–20000 code points, начинается с +, - или пробела», risk «1–1000 code points, непустая после trim»; дополнительные поля envelope игнорировать, нарушение даёт error без частичного результата.
- [X] T004 [US1] В static/app.js добавить POST /api/reviews с единственным исходным diff, loading, проверку HTTP/JSON и rendering через textContent/DOM: summary, «Возможные риски», checks, request_id, «ДЕМО» или реальный анализ; для 0 рисков оговорка об отсутствии гарантий, сторона строки из evidence, никаких активных ссылок или выполнения checks.

**Checkpoint**: минимальный success-path работает; завершающие защиты ожидания реализуются в US2 до окончательной приёмки.

## Phase 4: User Story 2 - Исправить вход или повторить анализ (Priority: P2)

**Goal**: понятный отказ, сохранение ввода, завершённое ожидание.  
**Independent Test**: пустой ввод/границы проверяются без модели; управляемые ошибки/задержки не требуют успешного анализа.

- [X] T005 [US2] В static/app.js реализовать счётчик и валидацию ReviewInput «1–20000 code points, не только пробельная», до trim/маскирования/нормализации, отправляя неизменённое textarea.value; локальная ошибка фокусирует поле и не вызывает fetch; серверные коды из contracts/ui-interface.md получают безопасный фиксированный текст, неизвестный код/плохой JSON/сеть — общий контролируемый отказ, ввод сохраняется.
- [X] T006 [US2] В static/app.js завершать активную попытку через 15000 мс с AbortController, номером Attempt и active guard для ответа/catch/finally; очищать таймер при любом финале, блокировать повторный submit и оба контрола на loading, игнорировать поздний ответ завершённой попытки, не запускать автоматические повторы.

## Phase 5: User Story 3 - Управлять просмотром без мыши (Priority: P3)

**Goal**: доступная форма, отзывчивый layout и явная очистка сеанса.  
**Independent Test**: клавиатура/status/очистка с управляемым результатом; ширина 360/1280 и масштаб 200%.

- [X] T007 [P] [US3] Создать static/styles.css с читаемой шириной, переносом длинных путей/evidence, контрастом текста ≥4.5:1, видимым focus-visible, текстовыми состояниями; на 360 CSS px и 200% не допускается горизонтальная прокрутка всей страницы, разрешена локальная прокрутка diff.
- [X] T008 [US3] В static/app.js добавить очистку/изменение → idle со скрытием старого результата и ошибки, при очистке фокусировать поле; связать validation error/aria-invalid с полем, обновлять доступные status/alert без неожиданного переноса фокуса после асинхронного результата; сохранить естественную клавиатуру формы static/index.html.

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T009 Проверить static/index.html, static/app.js и static/styles.css на отсутствие innerHTML для данных, постоянного хранения, console-логов содержимого и клиентских ключей; выполнить проверку синтаксиса JS и передать координатору готовые роли/имена для tests/test_e2e.py.
- [X] T010 Выполнить относящиеся к UI сценарии specs/001-review-ui/quickstart.md совместно с координатором после интеграции; исправить обнаруженные UI-дефекты в static/*, отметить фактическое выполнение задач и обновить specs/001-review-ui/checklists/requirements.md только по имеющимся результатам (screen reader не объявлять проверенным лишь по DOM).

## Dependencies & Execution Order

T001 → T002 → T003 → T004 → T005 → T006 → T008 → T009 → T010. T007 может идти независимо от JS-задач после T001. US2 пользуется общей state model, но проверяется независимо от успешной модели; US3 также проверяется с управляемым результатом. Для окончательной приёмки нужны все три stories и backend.

## Parallel Example: User Story 1

UI-задачи T003/T004 изменяют один static/app.js и идут последовательно. Одновременно команда логики реализует свой API в собственных файлах; это не дополнительная UI-задача.

## Parallel Example: User Story 2

T005/T006 идут последовательно в static/app.js. Координатор может независимо готовить управляемые ошибки в tests/test_e2e.py по утверждённой таблице.

## Parallel Example: User Story 3

T007 (static/styles.css) параллелится с T008 (static/app.js), когда T001 уже задаёт стабильные классы и DOM. В рамках одного исполнителя допустимо выполнить последовательно.

## Implementation Strategy

Сначала оболочка и success MVP US1, затем ошибки/таймеры US2, доступность/очистка US3, затем общий make check и ручные наблюдения. Ни demo, ни подмена HTTP не доказывают качество live-модели. Не коммитить без команды координатора. Реализация отмечена в checklist задач; T010 требует браузерных свидетельств координатора.

## Workflow evidence

setup-tasks.sh выполнен с явным SPECIFY_FEATURE_DIRECTORY=specs/001-review-ui и SPECIFY_FEATURE_NO_PERSIST=1; resolved TASKS_TEMPLATE_CONTENT и AVAILABLE_DOCS сохранены в tasks-setup.json. Шаблон применён соразмерно scope. `.specify/extensions.yml` отсутствует: pre/post hooks не требуются.

## Implementation progress (2026-10-27)

T001–T009 реализованы в static/index.html, static/app.js и static/styles.css. `node --check static/app.js` прошёл. Проверены уникальность DOM ids и ссылки label/ARIA, контраст активного текста (минимум среди проверенных пар 4.69:1), отсутствие innerHTML, persistent storage и console-вывода содержимого. Прочтение кода по spec подтвердило форму/границы результата, code point count, единичную попытку, 15-секундное ожидание, поздние ответы, безопасные ошибки и literal rendering. Статические проверки не заменяют браузерную приёмку.

T010 выполнена по browser proof координатора: tests/test_e2e.py — 10/10 PASS за 18.782s, evidence/e2e.txt. Проверены реальный UI→demo backend round-trip, границы, ошибки, 15-секундное ожидание и late response, literal rendering, клавиатура и reflow. Координатор визуально просмотрел ui-desktop.png, ui-mobile.png, ui-error.png: обрезаний/перекрытий нет. Семантические имена и DOM ids переданы координатору. Screen reader проверен только на уровне DOM/ARIA, не фактического озвучивания; live-label проверен управляемым ответом, не реальным вызовом модели. Checklist требований, spec/plan/contract и snapshots не изменялись. Hooks отсутствуют; команда UI git commit не создавала.
