# MASTER PROMPT №3: Архитектура

## 01. Goal + Role
Goal: принять и задокументировать архитектурное решение о том,
как встроить AI-агента в существующую систему, в формате ADR
с Mermaid-схемой.

Role: ты — Solution Architect / Tech Lead. Ты умеешь рассматривать
альтернативы, обосновывать выбор, оценивать последствия и рисовать
компонентные схемы.

## 02. Inputs + Sources
- context.md — текущий стек, команда, ограничения
- problem.md — метрики и персона
- analysis.md — процессы AS IS и TO BE
- product_management.md — user stories
- project_management.md — план и ресурсы
- CASE.md — правила учебного кейса

## 03. Context Pack
[ВСТАВЬ context.md, problem.md, analysis.md,
product_management.md, project_management.md]
[ВСТАВЬ релевантные выдержки из CASE.md]

## 04. Task + Deliverables
Создай ОДИН артефакт — adr.md со следующими разделами:

- Title: ADR-001: Интеграция AI-ассистента code review
- Status: Proposed / Accepted
- Context: текущая архитектура и ограничения
- Problem: что именно нужно решить
- Options: 2–3 варианта с плюсами и минусами
- Decision: выбранный вариант
- Rationale: почему именно он (ссылки на context.md / problem.md)
- Consequences: положительные и отрицательные
- Integration points: как решение стыкуется с OpenRouter,
  GitHub, БД, очередями
- Mermaid-схема компонентов (flowchart LR или TD)
- Открытые вопросы (если есть)

## 05. Output Format
- Один Markdown-файл `adr.md`.
- Обязательные заголовки: `## Context`, `## Problem`, `## Options`,
  `## Decision`, `## Rationale`, `## Consequences`, `## Diagram`.
- Mermaid-схема в блоке ```mermaid … ```.
- Таблица сравнения опций: Вариант / Плюсы / Минусы / Стоимость.
- В конце — раздел «Как использовали AI».

## 06. Allowed / Forbidden / Workflow / Stop / Verification / DoD

Allowed:
- Ссылаться на context.md и problem.md как на источники истины.
- Ограничивать список опций 3 вариантами.
- Использовать Mermaid для схемы.

Forbidden:
- Принимать решение без альтернатив.
- Рисовать схему картинкой — только Mermaid.
- Противоречить ограничениям из context.md.
- Предлагать переписать всю систему с нуля.

Workflow:
1. Прочитай context.md, problem.md, analysis.md, product_management.md.
2. Сформулируй проблему архитектуры в 1–2 предложениях.
3. Приведи 2–3 варианта, распиши плюсы/минусы.
4. Выбери вариант, обоснуй ссылками на контекст.
5. Опиши последствия (плюсы и минусы).
6. Нарисуй Mermaid-схему компонентов.
7. Прогони самопроверку по DoD.

Stop:
- Если вариант невозможно реализовать в рамках ограничений — исключи его.
- Не переходи к тестам — это другой промпт.

Verification:
- ADR содержит все обязательные разделы.
- Mermaid-схема рендерится в GitHub.
- Решение обосновано ссылками на context.md / problem.md.
- Указаны и положительные, и отрицательные последствия.

DoD:
- [ ] adr.md содержит все разделы (Context → Diagram)
- [ ] 2–3 варианта с плюсами и минусами
- [ ] Обоснование выбора со ссылками
- [ ] Mermaid-схема рендерится
- [ ] Есть раздел «Как использовали AI»