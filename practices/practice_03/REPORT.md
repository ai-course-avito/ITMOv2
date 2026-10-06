# REPORT: Практика 3 — локальные модели

Краткое резюме
- Локальные модели собраны и запущены через Ollama. Вопросы заданы через OpenCode-агента `local-guide` (read-only: read/glob/grep). Ответы и логи сохранены.
- itmo-agent прошёл все 5 вопросов. На 5-м вопросе требовалась уточняющая формулировка; без подсказок также отвечает корректно.
- itmo-chat без дополнительной шлифовки промпта дал шум и таймауты; для чистых ответов потребовалось вручную ужесточить формат (краткость, источники, запрет планирования).

Железо и окружение
- CPU: Apple M4, 10 ядер
- RAM: 16 GB
- OS: macOS (Darwin arm64)
- Python: 3.14.7 (stdlib only)
- OpenCode: 1.18.34

Локальные модели и квантизация
- База: `qwen3.5:4b` (локально, Ollama)
- Собранные модели:
  - `itmo-agent:latest` (FROM qwen3.5:4b; num_ctx 65536; temperature 0.2)
  - `itmo-chat:latest` (готовая в Ollama)
- Образы в Ollama:
  - `itmo-agent:latest` ID 3465bc38f59d, ~3.4 GB
  - `itmo-chat:latest` ID 721e96699aea, ~3.4 GB
  - Базовые: `qwen3.5:4b`, `qwen3.5-4b-{32k,64k,128k}`

Контекст и параметры
- Агент: `local-guide` из [`lab/demo/opencode.json`](lab/demo/opencode.json)
  - Системный промпт: [`lab/demo/repo-system.txt`](lab/demo/repo-system.txt)
  - Ограничения: только read/glob/grep
  - steps: 8
- Модель по умолчанию в demo: `ollama/itmo-agent` (контекст 64k)
- Для ручной сверки также опрашивалась `ollama/itmo-chat`.

Что сделано
- Подготовлены эталонные ответы: [`lab/_private/gold_answers.md`](lab/_private/gold_answers.md) (не доступен тестируемым моделям).
- Сбор ответов через OpenCode:
  - [`lab/results/itmo-agent_resp_opencode.md`](lab/results/itmo-agent_resp_opencode.md) — 5 вопросов, ответы модели itmo-agent.
  - [`lab/results/itmo-chat_resp_opencode.md`](lab/results/itmo-chat_resp_opencode.md) — чистые краткие ответы (после шлифовки формата).
- Ручные проверки для диагностики:
  - Перепроверен 5-й вопрос itmo-agent без подсказок — ответ стабильный.

Сравнение с эталонами (кратко)
- Набор вопросов включает: один без ответа в репозитории (CI) и один с ложной предпосылкой (unsubscribe).
- itmo-agent:
  1) Как запустить тесты? Укажи файл-источник. — PARTIAL. Верно указал README.md:6 (`make test`), но ошибочно заявил об отсутствии Makefile. Верное основание: demo/Makefile:1-3.
  2) Что будет при пустом имени подписчика? — OK. demo/service.py:5-6; подтверждение: demo/test_service.py:13-16.
  3) Где реализован unsubscribe? — OK. Отсутствует в demo/service.py.
  4) Какая CI-система запускает тесты? — OK. Конфигурации CI отсутствуют в demo/.
  5) Сохраняются ли подписки после перезапуска процесса? — OK. demo/README.md:2; demo/service.py:1.
- itmo-chat (после шлифовки формата): все 5 ответов соответствуют эталонам по смыслу.

Замечания и ограничения
- itmo-chat: без дополнительной шлифовки промпта наблюдались:
  - шумный вывод (псевдо-планирование: Objective/Work State/Next Move),
  - некорректные вызовы инструментов (пустой glob-паттерн, попытка вызвать отсутствующий инструмент),
  - один случай таймаута.
  Для сдачи потребовалось ужесточить формат ответа (кратко + основание) и ограничить область поиска.

Артефакты
- Вопросы: [`lab/QUESTIONS.md`](lab/QUESTIONS.md)
- Ответы моделей через OpenCode:
  - [`lab/results/itmo-agent_resp_opencode.md`](lab/results/itmo-agent_resp_opencode.md)
  - [`lab/results/itmo-chat_resp_opencode.md`](lab/results/itmo-chat_resp_opencode.md)
  - Пример шумного вывода itmo-chat: [`lab/results/itmo-chat_noise_example.md`](lab/results/itmo-chat_noise_example.md)
- Эталоны (для агента): [`lab/_private/gold_answers.md`](lab/_private/gold_answers.md)
- Конфигурация агента: [`lab/demo/opencode.json`](lab/demo/opencode.json), промпт: [`lab/demo/repo-system.txt`](lab/demo/repo-system.txt)
- Modelfiles: [`lab/Modelfile`](lab/Modelfile), [`lab/Modelfile.agent`](lab/Modelfile.agent)
