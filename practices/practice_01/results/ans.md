### 01. Goal + Role
- Роль: Ведущий системный инженер / технический писатель (OpenCode Build)[cite: 6, 7].
- Цель: Заполнить и согласовать 11 файлов практики по кейсу AI-ревьюера PR перед сдачей[cite: 6, 7].

### 02. Inputs + Sources + Context Pack
- Входы: TRAINING_PR.diff, результаты запусков P1-01 и P1-02, журнал prompts.md[cite: 7].
- Контекст: FastAPI-сервис; риски — KeyError: diff (500), сбои вызова LLM (500), нет response_model; решение — Pydantic-схемы, try/except (422, 502)[cite: 7].

### 03. Task + Deliverables
- Задача: Заполнить в practices/practice_01/ все 11 файлов (context, problem, analysis, product_management, project_management, adr, tests_unit, tests_integration, tests_load, tests_e2e, prompts)[cite: 7].
- Требования:
  * Заполнить все таблицы во всех файлах; таблицу «Peer Review» оставить пустой для проверяющего[cite: 7].
  * В файлы 1–10 включить блок «Как использовали AI» со ссылкой на prompts.md[cite: 7].
- Deliverables: 11 обновленных файлов в файловой системе[cite: 7].

### 04. Output Format
- Модификация файлов на месте в practices/practice_01/[cite: 6].
- В чат: статус-список 11 файлов, diff изменений и способ проверки[cite: 6, 7].

### 05. Allowed / Forbidden + Stop
- Разрешено: Редактировать и создавать файлы в practices/practice_01/[cite: 6].
- Запрещено: Заполнять Peer Review, оставлять TODO/TBD и противоречия между рисками и тестами.
- Stop: Остановка сразу после сохранения 11 файлов и вывода diff[cite: 6, 7].

### 06. Workflow + Verification + DoD
- Workflow: Анализ текущих файлов -> Заполнение таблиц и секций (кроме Peer Review) -> Добавление блоков «Как использовали AI» -> Проверка целостности[cite: 7].
- Verification: Поиск отсутствия TODO/TBD через grep; согласованность рисков и тестов.
- DoD: 11 файлов заполнены без заглушек, таблица Peer Review не тронута, diff показан[cite: 6, 7].