# Отчёт: локальные модели

Отчёт ведёт OpenCode по фактическим результатам команд и вашим сообщениям в чате. Поручите агенту заполнить разделы и показать diff. Выводы студента он записывает после обсуждения; отсутствующие измерения отмечает как невыполненные.

## Окружение

ОС / CPU / GPU / RAM / VRAM / свободный диск:
- Windows; AMD Ryzen AI 9 HX 370 (12C/24T); AMD Radeon 890M (iGPU, DirectML); RAM 32 GB; VRAM shared; диск: н/д
Ollama или LM Studio / OpenCode / Python, версии:
- Ollama 0.34.4; OpenCode: запуск команды заблокирован политикой PowerShell (ExecutionPolicy); Python 3.14.0
Модель, разработчик, семейство, тег и ID:
- Qwen2.5 Instruct 7B, тег qwen2.5:7b-instruct-q4_k_m; локальный образ itmo-local/itmo-agent; ID см. `ollama list`
Формат, квантизация, лицензия, источник:
- GGUF через Ollama; квантовка Q4_K_M; лицензия Apache-2.0; источник ollama pull (локально успешно)
Фактический контекст, размещение CPU/GPU:
- itmo-local num_ctx=4096; itmo-agent: параметр num_ctx=65536, фактический контекст по `ollama show`: 32768; размещение: 100% CPU (ollama ps)
Почему выбрана эта конфигурация:
- Русский язык обязателен и нужны кодовые навыки; Qwen2.5 7B Instruct даёт хороший баланс качества/ресурсов на 32 GB RAM.

## Сравнение семейств

| Разработчик / модель | Задача | Параметры / формат | Лицензия | Язык / tools | Источник |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |

## Воспроизведение

Команды и файлы конфигурации:
- Обновлены lab/Modelfile и lab/Modelfile.agent на FROM qwen2.5:7b-instruct-q4_k_m
- Создание образов: `ollama create itmo-local -f lab/Modelfile`, `ollama create itmo-agent -f lab/Modelfile.agent`
- Проверка модели: `ollama run itmo-local "Объясни разницу..."`, `ollama show itmo-agent`, `ollama ps`
Подтверждение локального endpoint и скачанных весов:
- `ollama list` показывает qwen2.5:7b-instruct-q4_k_m (~4.7 GB); API доступен на http://localhost:11434
Проверка без сети после подготовки:
- не выполнялась в этой сессии
Если работали в паре, чей компьютер и почему:
- н/д
 - OpenCode local-guide:
   - opencode 1.18.33, запуск через временный Bypass ExecutionPolicy на процесс
   - Вопрос о README: results/local-guide-q1.jsonl (подтверждён read и ответ «make test»)
   - Вопросы q2–q5: results/local-guide-q2.jsonl … q5.jsonl (read по файлам и ответы)
   - Повторные запросы q3b–q5b с уточнённой формулировкой: results/local-guide-q3b.jsonl … q5b.jsonl
 - Юнит-тесты:
   - python -m unittest -v (demo/) → все 3 теста OK; вывод доступен в терминале

## Эксперимент

Фактор A/B:
- baseline (без system) vs system (system.txt), одна и та же модель itmo-local
Неизменные условия:
- Вход: контекст из demo/README.md, demo/service.py, demo/test_service.py; пять вопросов из lab/QUESTIONS.md; temperature=0.2; seeds 42/43/44; think=false; num_ctx=4096
| Вопрос | Эталон и file:line | Ответ A | Ответ B | Верно A/B | Наблюдение инструментов |
|---|---|---|---|---|---|
| Как запустить тесты? | make test — demo/README.md:6; файл тестов demo/test_service.py:1 | Файл-источник demo/test_service.py; (лишнее: python -m unittest) | Файл-источник demo/test_service.py; основание README.md:6 | A≈OK, B=OK | API /api/chat |
| Пустое имя подписчика | ValueError — service.py:5–6; test_service.py:13–15 | ValueError; подтверждение по коду | «нет ответа» + код с ValueError | A=OK, B=OK по сути | API /api/chat |
| Где unsubscribe | Отсутствует — service.py, test_service.py | «нет ответа», основания указаны | «нет ответа», основания указаны | A=OK, B=OK | API /api/chat |
| Какая CI | «нет сведений», README.md | «нет ответа», основание верное | «нет ответа», основание верное | A=OK, B=OK | API /api/chat |
| Перезапуск процесса | Данные теряются (in-memory), README.md:2 | «нет ответа» (объяснение без явного вывода) | «нет ответа» + явный вывод «утрачены при перезапуске» | A=OK, B=OK | API /api/chat |

## Скорость

Холодный старт отдельно:
- не измеряли отдельно
Три прогретых повтора и медиана:
- A/B по 5 вопросам: медианы сохранены в lab/results/ab_summary.json; decode_tps A≈5.8–6.3, B≈5.6–6.2; total_seconds A≈5.8–21.8, B≈10.0–13.3
Единицы и метод замера:
- eval_duration/total_duration из ответа Ollama; decode_tokens_per_second посчитан скриптом
TTFT измерен или не измерен:
- не измерен (непотоковый ответ)

## Вывод

Ошибка или обнаруженное ограничение:
- Фактический максимальный контекст у itmo-agent 32768, несмотря на запрошенные 65536; OpenCode CLI заблокирован ExecutionPolicy; make отсутствует в Windows окружении.
Как проверили:
- `ollama show itmo-agent`, `ollama ps`; попытка `opencode run` показала ошибку ExecutionPolicy.
Какой конфигурацией будете пользоваться:
- Оставляем qwen2.5:7b-instruct-q4_k_m с temperature=0.2 для кода и вопросов по проекту.
Что осталось непроверенным:
- Полноценный прогон через make (рекомендуется WSL) и повтор A/B с альтернативным system prompt.
