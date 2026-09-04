Role: Lead SDLC Architect.
Goal: Спроектировать и заполнить оставшиеся проектные артефакты для сервиса AI-ревьюера PR по правилам из CASE.md.
Inputs: @CASE.md, @context.md, @answer_1_01.md, @answer_1_02.md.
Return: Заполненные артефакты проекта со строгим сохранением заголовков шаблонов (особенно «## Метрики»), mermaid-схем и gherkin.
Forbidden: Удалять существующие заголовки шаблонов, выдумывать несвязанные с кейсом правила.
Flow: Проблема и метрики → Процесс и Use Cases → Архитектура (ADR) → Тест-кейсы → prompts.md.
Outputs: @problem.md, @analysis.md, @product_management.md, @project_management.md, @adr.md, @tests_unit.md, @tests_integration.md, @tests_load.md, @tests_e2e.md, @prompts.md.
Finish: Заполни указанные файлы по кейсу AI-ревьюера (правила SEC-1...OBS-1), везде в блоке «Как использовали AI» укажи строку P1-03, в prompts.md добавь строку P1-03.
