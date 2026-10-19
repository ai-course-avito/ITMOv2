# Установка Ollama и модели qwen3.5:4b

Дата: 2026-10-07. Windows 11 Pro. Файл для себя, в git не коммитил.

## Железо

| Что | Значение |
|---|---|
| Процессор | Intel Core Ultra 5 225H, 14 ядер / 14 потоков |
| RAM | 31.4 GB |
| Видеокарта | Intel Arc 130T (встроенная, "16GB" общая память), драйвер 32.0.101.6554 |
| Отдельной NVIDIA/AMD нет | `nvidia-smi` не найден |
| Диск C: | свободно 531.6 GB |
| Диск D: | свободно 21.3 GB |

Важно: у меня нет выделенной видеокарты, поэтому модель считается на процессоре (см. `ollama ps` ниже).

## Установка

- Команда: `winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements`
- winget сработал с первого раза, скачивать установщик руками не пришлось.
- Версия: **ollama 0.40.0**
- Путь: `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` (в уже открытой сессии PATH мог не обновиться, поэтому использовал полный путь)
- Сервер сам запустился после установки, `http://localhost:11434/api/version` вернул `{"version":"0.40.0"}`.

## Скачивание модели

- Команда: `ollama pull qwen3.5:4b`
- Запускал в фоне, прогресс писался в лог. Заняло около 3-4 минут (скорость ~26 MB/s), оборвов не было, закончилось `success`.
- Слои: 675 MB + 2.6 GB + мелкие (манифест, параметры). Размер на диске по `ollama list`: **3.3 GB**.
- ID модели: **d8b0f5e9760c**

## ollama show qwen3.5:4b

```
  Model
    architecture        qwen35
    parameters          4.2B
    context length      262144
    embedding length    2560
    quantization        Q4_K_M
    requires            0.30.0

  Capabilities
    completion
    vision
    tools
    thinking
        levels     false, true
        default    true

  Projector
    architecture        clip
    parameters          333.51M
    embedding length    1024
    dimensions          2560

  Parameters
    temperature         1
    top_k               20
    top_p               0.95
    presence_penalty    1.5

  License
    Apache License
    Version 2.0, January 2004
```

Заметка: Ollama показывает 4.2B параметров (текстовая часть), а в README практики написано 4.7B. Вероятно, 4.7B считается вместе с vision-проектором (4.2B + 0.33B это ещё не 4.7B, так что цифры расходятся; для отчёта лучше ссылаться на то, что выдаёт `ollama show`). Размер файла ~3.3 GB (в README ~3.4 GB), это нормально.

## ollama list

```
NAME                 ID              SIZE      MODIFIED
itmo-local:latest    bbaeb7f8d84a    3.3 GB    6 minutes ago
qwen3.5:4b           d8b0f5e9760c    3.3 GB    8 minutes ago
```

`itmo-local:latest` я не создавал. Он появился уже после моего pull (наверное, его собрали из `lab/Modelfile`, там `FROM qwen3.5:4b`). Я его не трогал.

## ollama ps (после тестового запроса)

```
NAME          ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL
qwen3.5:4b    d8b0f5e9760c    3.1 GB    100% CPU     4096       llamacpp    4 minutes from now
```

Работает на 100% CPU, GPU (Intel Arc) не используется.

## Тестовый запрос и скорость

Запрос к `/api/chat`: `stream=false`, `think=false`, `num_predict=64`, вопрос "Объясни простыми словами, что такое локальная языковая модель."

Ответ (обрезался по лимиту 64 токенов, `done_reason=length`): "Локальная языковая модель (Local LLM) - это нейросеть, которая установлена и работает на вашем устройстве ... а не в облаке ..." Русский язык нормальный.

| Метрика | Значение |
|---|---|
| eval_count | 64 токена |
| eval_duration | 6.30 с |
| **Скорость генерации** | **~10.2 tokens/sec** (64 / 6.30) |
| Разбор промпта | 28 токенов, ~48 tokens/sec |
| Загрузка модели в память (первый запрос) | 9.2 с |

Скорость на CPU небольшая, для практики хватает, но длинные ответы будут идти медленно. Поэтому в Modelfile стоят ограничения `num_ctx 2048`, `num_predict 128`.

## Есть ли модель сильнее около 4.5B

Страницу ollama.com/library напрямую открыть не удалось (WebFetch не смог проверить домен), поэтому смотрел обзоры через поиск: конкуренты в этом классе это gemma3:4b и phi4-mini:3.8b, но они не выглядят явно сильнее qwen3.5:4b (у qwen3.5:4b есть thinking, tools, vision, контекст 256K). Вторую модель не скачивал.

## Проблемы

- Серьёзных нет. Установка и pull прошли с первого раза.
- Прогресс `ollama pull` пишется в stderr, а не в stdout, поэтому лог stdout получился пустым.
- На ноутбуке нет дискретной GPU, всё считается на CPU (~10 tok/s).
- OpenCode не ставил и не запускал. Файлы репозитория не менял, кроме этого нового файла.
