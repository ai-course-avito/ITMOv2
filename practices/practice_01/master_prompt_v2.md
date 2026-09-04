# Master Prompt v2 (заполнение оставшихся артефактов, Build-режим)

Role: Lead SDLC Architect + AI code reviewer. Работаешь в режиме Build — можешь редактировать только перечисленные ниже файлы.

Goal: спроектировать и заполнить оставшиеся проектные артефакты для сервиса AI-ревьюера PR (ReviewService из TRAINING_PR.diff) по правилам из CASE.md — так, чтобы все файлы описывали один и тот же согласованный сценарий.

Inputs (единственные источники фактов, дальше не выходить):
@CASE.md, @context.md, @problem.md, @TRAINING_PR.diff, @master_prompt_v1.md, @P1-02.md

Outputs (заполнить, сохраняя структуру шаблонов):
@analysis.md, @product_management.md, @project_management.md, @adr.md, @tests_unit.md, @tests_integration.md, @tests_load.md, @tests_e2e.md

problem.md, context.md и prompts.md НЕ трогать — заполняются человеком отдельно.

Flow (заполняй строго в этом порядке, каждый следующий файл должен быть согласован с предыдущим):
1. analysis.md — AS IS/TO BE процесса ревью PR
2. product_management.md — use case и user stories на основе problem.md
3. project_management.md — план инкрементов, реализующих use case из шага 2
4. adr.md — архитектурное решение, покрывающее инкременты из шага 3
5. tests_unit.md, tests_integration.md, tests_load.md, tests_e2e.md — тесты на решение из ADR

Rules:
- Каждое утверждение опирается на CASE.md, context.md, problem.md или конкретную строку TRAINING_PR.diff. Если факта нет ни в одном источнике — пиши "требует уточнения" прямо в поле, не выдумывай правдоподобное значение.
- Mermaid-диаграммы и gherkin-сценарии должны буквально описывать этот кейс (LLM-ревью diff через ReviewService), а не оставаться шаблонным placeholder-текстом.
- Тесты ссылаются на конкретные правила (SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1) и конкретные строки/поведение из TRAINING_PR.diff — без общих фраз вроде "проверить корректность".
- В каждом заполненном файле заполни секцию "Как использовали AI": Для чего — конкретика под этот файл, Тип промпта — master prompt (build), Строка в prompts.md — P1-03, Что проверили и исправили сами — оставить пустым для человека.

Forbidden:
- Удалять или менять существующие заголовки шаблонов, особенно "## Метрики".
- Редактировать context.md, problem.md или prompts.md.
- Выдумывать правила, не входящие в SEC-1...OBS-1.
- Approve, merge, любые действия вне указанных 8 файлов.

Done: во всех 8 output-файлов нет пустых полей/таблиц/mermaid-заглушек, каждый согласован с предыдущим по Flow, context.md/problem.md/prompts.md остались без изменений.