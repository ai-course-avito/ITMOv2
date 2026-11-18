# Практика 3 — подключение LLM через OpenCode

## Цель и задачи
- Запуск локальной LLM и интеграция в OpenCode; сравнение baseline vs system; эксперименты temperature/seed

## Что такое OpenCode
- Конфигурация: opencode.json; MCP context7; провайдеры VseLLM и Ollama для demo

## Подключение Qwen 3 через провайдера (на основе opencode.json)
- demo/opencode.json: baseURL http://localhost:11434/v1; модель itmo-agent с context 65536

## Настройка агента и скиллов
- local-guide: read-only, prompt из repo-system.txt; разрешены read/glob/grep

## Тестирование модели: сценарии и результаты
- baseline/system из PRACTICE.md; метрики и чтение файлов фиксируются в results/*.json{,l}

## Артефакты в results/
- practices/practice_03/lab/results/baseline.json
- practices/practice_03/lab/results/cool42.json
- practices/practice_03/lab/results/cool43.json
- practices/practice_03/lab/results/cool44.json
- practices/practice_03/lab/results/hot42.json
- practices/practice_03/lab/results/hot43.json
- practices/practice_03/lab/results/hot44.json
- practices/practice_03/lab/results/q1.jsonl
- practices/practice_03/lab/results/q2.jsonl
- practices/practice_03/lab/results/q3.jsonl
- practices/practice_03/lab/results/q4.jsonl
- practices/practice_03/lab/results/q5.jsonl
- practices/practice_03/lab/results/read-check.jsonl
- practices/practice_03/lab/results/read-check2.jsonl
- practices/practice_03/lab/results/read-check3.jsonl
- practices/practice_03/lab/results/system.json

## Выводы и дальнейшие шаги
- Модель не выдумывает при отсутствии данных; TTFT не измерён; расширить сравнение моделей
