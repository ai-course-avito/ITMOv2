# Отчёт: локальные модели

Отчёт ведёт OpenCode по фактическим результатам команд и вашим сообщениям в чате. Поручите агенту заполнить разделы и показать diff. Выводы студента он записывает после обсуждения; отсутствующие измерения отмечает как невыполненные.

## Окружение

ОС / CPU / GPU / RAM / VRAM / свободный диск: Linux (uname -a см. лог). CPU: Intel Core i7-10700F. RAM: 16 GB DDR4. GPU: NVIDIA GeForce RTX 3060 Ti (VRAM 8 GB). Свободный диск: не фиксировался.
Ollama / OpenCode / Python, версии: Ollama 0.34.4; OpenCode 1.18.27; Python 3.10+ (Makefile check).
Модель, разработчик, семейство, тег и ID: qwen3.5:9b (Ollama), family qwen35; локальные теги `itmo-local`, `itmo-agent`.
Формат, квантизация, лицензия, источник: Q4_K_M; Apache-2.0; источник — Ollama `qwen3.5:9b`.
Фактический контекст, размещение CPU/GPU: `itmo-agent` контекст 65536; процессор 36% CPU / 64% GPU (ollama ps).
Почему выбрана эта конфигурация: доступные веса в локальном кэше, достаточный контекст для чтения репозитория; единый фактор A/B — system prompt.

## Сравнение семейств

| Разработчик / модель | Задача | Параметры / формат | Лицензия | Язык / tools | Источник |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |

## Воспроизведение

Команды и файлы конфигурации:
 - Обновлены Modelfile/Modelfile.agent на `qwen3.5:9b`.
 - Сборка и проверка:
   `mkdir -p lab/results`
   `ollama create itmo-local -f lab/Modelfile`
   `ollama run itmo-local "..."`
   `python3 lab/experiment.py --mode baseline --output lab/results/baseline.json`
   `python3 lab/experiment.py --mode system --output lab/results/system.json`
Подтверждение локального endpoint и скачанных весов: `curl --fail http://localhost:11434/api/tags`; `ollama list` показывает `qwen3.5:9b`.
Проверка без сети после подготовки: локальные обращения успешно завершаются.
Если работали в паре, чей компьютер и почему: одиночный запуск.

## Эксперимент

Фактор A/B: различие system prompt (A — [lab/demo/repo-system-a.txt](lab/demo/repo-system-a.txt); B — [lab/demo/repo-system-b.txt](lab/demo/repo-system-b.txt)). Модель и параметры одинаковые.
Неизменные условия: модель `ollama/itmo-agent`, temperature=0.2, seed=42, контекст одинаковый, режим без think.
| Вопрос | Эталон и file:line | Ответ A | Ответ B | Верно A/B | Наблюдение инструментов |
|---|---|---|---|---|---|
| Q1 Как запустить тесты? | [lab/demo/README.md](lab/demo/README.md):6; [lab/demo/Makefile](lab/demo/Makefile):1-3 | [см. ответ A](lab/results/answers.md#q1-как-запустить-тесты-укажи-файл-источник) | [см. ответ B](lab/results/answers.md#q1-как-запустить-тесты-укажи-файл-источник) | Оба верны | read: README.md и/или Makefile |
| Q2 Пустое имя | [lab/demo/service.py](lab/demo/service.py):5-7; [lab/demo/test_service.py](lab/demo/test_service.py):14-16 | [см. ответ A](lab/results/answers.md#q2-что-будет-при-пустом-имени-подписчика-подтверди-кодом) | [см. ответ B](lab/results/answers.md#q2-что-будет-при-пустом-имени-подписчика-подтверди-кодом) | Оба верны | read: service.py |
| Q3 unsubscribe | отсутствует | [см. ответ A](lab/results/answers.md#q3-где-реализован-unsubscribe-проверь-предпосылку-вопроса) | [см. ответ B](lab/results/answers.md#q3-где-реализован-unsubscribe-проверь-предпосылку-вопроса) | Оба верны | grep: нет совпадений |
| Q4 CI | нет сведений | [см. ответ A](lab/results/answers.md#q4-какая-ci-система-запускает-тесты-если-сведений-нет-скажи-об-этом) | [см. ответ B](lab/results/answers.md#q4-какая-ci-система-запускает-тесты-если-сведений-нет-скажи-об-этом) | Оба верны | glob: нет файлов CI; read: README.md |
| Q5 Персистентность | [lab/demo/service.py](lab/demo/service.py):1; [lab/demo/README.md](lab/demo/README.md):2 | [см. ответ A](lab/results/answers.md#q5-сохраняются-ли-подписки-после-перезапуска-процесса-подтверди-кодом) | [см. ответ B](lab/results/answers.md#q5-сохраняются-ли-подписки-после-перезапуска-процесса-подтверди-кодом) | Оба верны | read: service.py, README.md |

## Скорость

Холодный старт отдельно: baseline/system первый запуск ~15.6s wall (включая загрузку ~11.1s).
Три прогретых повтора и медиана: baseline прогретые wall ~4.66/4.62/4.59s; system прогретые ~4.69/4.58/4.55s; медиана ~4.62s. Скорость декодирования ~78-82 ток/с.
Единицы и метод замера: wall_seconds по ответу Ollama API; eval_duration для расчёта ток/с.
TTFT измерен или не измерен: не измерен (непотоковый ответ).

## Вывод

Ошибка или обнаруженное ограничение: модель правильно отказывалась выдумывать CI, подтверждая отсутствие сведений (system). Различие system prompt влияет на стиль ссылок (file:line vs path-only), точность сопоставима.
Как проверили: отдельные сессии `opencode run` для каждого вопроса; сохранены ответы и tool events в `lab/results/*.jsonl`.
Какой конфигурацией будете пользоваться: оставляем B (repo-system-b.txt) — чуть более нейтральная формулировка, та же точность.
Что осталось непроверенным: TTFT не измерен.
