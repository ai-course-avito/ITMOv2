# Отчет по Практике 5: Spec-Driven Development (OpenSpec)

Этот отчет описывает процесс выполнения Практики 5 по курсу «Инструменты AI-инжиниринга» в рамках сквозного проекта **AlgoPlace** (платформа для алгоритмических тренировок и онлайн-судейства).

---

## 1. Контекст задачи и выбор фичи

В качестве третьей ключевой фичи (User Story) для проекта AlgoPlace была выбрана **История посылок пользователя (Submission History)**:
> **User Story:** *«Как авторизованный пользователь AlgoPlace, я хочу просматривать историю своих прошлых попыток решения задачи (вердикт, рантайм, использованная память, отправленный код) и иметь возможность восстановить решение в редактор, чтобы отслеживать свой прогресс и возвращаться к удачным реализациям»*.

Разработка велась строго по методологии **Spec-Driven Development (SDD)**: спецификация и контракты были полностью согласованы **до** написания первой строчки кода.

---

## 2. Разделение и согласование спецификаций (UI & Backend)

Согласно требованиям практики, фича была декомпозирована на два согласованных направления:

### 2.1 Спека логики и данных (Backend API)
- **Контракт:** `GET /api/problems/{id}/submissions` (защищен JWT авторизацией).
- **Схема ответа:** Массив объектов `SubmissionRecord` с полями:
  - `id` (string/int)
  - `problem_id` (string)
  - `language` (string: python, cpp, javascript)
  - `code` (string)
  - `status` (string: Accepted, Wrong Answer, Time Limit Exceeded)
  - `runtime_ms` (int), `memory_mb` (int)
  - `passed_tests` / `total_tests` (int)
  - `created_at` (RFC3339 timestamp)
- **Edge-кейсы:**
  - Неавторизованный запрос возвращает HTTP 401 Unauthorized.
  - Если у пользователя нет сабмитов по задаче, возвращается HTTP 200 и пустой массив `[]` (не null и не 404).
  - Сортировка строго `ORDER BY created_at DESC LIMIT 20`.

### 2.2 Спека пользовательского интерфейса (Frontend UI)
- **Размещение:** Вкладка `Submissions` в левой панели компонента `ProblemWorkspace` (рядом с `Description`).
- **Состояния:**
  - *Гость (не залогинен):* Вкладка `Submissions` скрыта; доступна только `Description`.
  - *Авторизованный пользователь:* Вкладка отображается, при открытии загружает список последних сабмитов.
  - *Инспекция кода:* Клик по строке открывает модальное окно просмотра с подсветкой синтаксиса и детальными метриками вердикта.
  - *Восстановление:* Кнопка `Restore to editor` загружает код выбранной попытки в активный Monaco Editor и переключает язык в дропдауне.

---

## 3. Артефакты OpenSpec

В ходе цикла SDD были сформированы и проверены артефакты (сохранены в `practices/practice_05/`):
1. **[`proposal.md`](proposal.md)** — мотивация, User Story, границы изменений (scope/out of scope) и архитектурное влияние.
2. **[`design.md`](design.md)** — архитектурные решения, выбор маршрутов API, схема взаимодействия с БД без изменения схемы (reuse таблицы `submissions`), управление рисками случайной перезаписи кода.
3. **[`specs/submission-history/spec.md`](specs/submission-history/spec.md)** — формализованные требования в стиле Given/When/Then.
4. **[`tasks.md`](tasks.md)** — пошаговый план задач, по которому агент реализовал бэкенд, фронтенд и тесты.

---

## 4. Реализация и автоматическая верификация

После ревью и согласования спецификации агент выполнил реализацию строго по пунктам `tasks.md`:
1. **Бэкенд (Go):**
   - Добавлена модель `SubmissionRecord` в `internal/models/problem.go`.
   - Реализован метод репозитория `GetSubmissions` в `internal/repository/postgres.go` и моках.
   - Реализован HTTP-хэндлер `GetProblemSubmissions` в `internal/handlers/api.go`.
   - Покрыто юнит-тестами в `internal/handlers/api_test.go` (проверка 200, 401, пустых списков).
2. **Фронтенд (React 19 + TypeScript):**
   - Добавлен интерфейс `Submission` в `src/types/problem.ts`.
   - Метод `getSubmissions` в `src/services/api.ts`.
   - Интеграция вкладки `Submissions` и модального окна просмотра/восстановления в `ProblemWorkspace.tsx`.
   - Покрыто тестами в `ProblemWorkspace.test.tsx` и `api.test.ts`.

### Результат прогона обязательного хука `./scripts/verify-tests.sh`:
```bash
==========================================
 [HOOK] Running AlgoPlace Verification Suite
==========================================
--> 1. Verifying Frontend (TypeScript & Vite production build)...
✓ built in 316ms
--> 2. Verifying Backend (Go Unit & Runner Tests)...
=== RUN   TestGenerateAndValidateToken
--- PASS: TestGenerateAndValidateToken (0.00s)
=== RUN   TestGetProblems_And_GetProblemBySlug
--- PASS: TestGetProblems_And_GetProblemBySlug (0.00s)
=== RUN   TestRunCode
--- PASS: TestRunCode (0.00s)
=== RUN   TestSubmitCode
--- PASS: TestSubmitCode (0.00s)
=== RUN   TestAdminHandlers
--- PASS: TestAdminHandlers (0.00s)
=== RUN   TestUserJSONSerialization
--- PASS: TestUserJSONSerialization (0.00s)
=== RUN   TestProblemJSONSerialization
--- PASS: TestProblemJSONSerialization (0.00s)
=== RUN   TestDefaultRepository
--- PASS: TestDefaultRepository (0.00s)
=== RUN   TestExecutePythonSuccess
--- PASS: TestExecutePythonSuccess (0.03s)
=== RUN   TestExecuteTimeout
--- PASS: TestExecuteTimeout (4.00s)
PASS
==========================================
 [HOOK PASSED] All tests & builds passed!
==========================================
```

---

## 5. Завершение жизненного цикла (Archive)

По завершении реализации и прохождения всех проверок изменение было заархивировано через OpenSpec CLI:
```bash
openspec archive 2026-10-25-submissions-history --yes
```
Спецификация фичи переместилась в постоянный реестр спецификаций `openspec/specs/submission-history/spec.md`, зафиксировав актуальный контракт системы.
