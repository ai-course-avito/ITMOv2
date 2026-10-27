# AI PR Reviewer — ДЗ 5

Одностраничный помощник: вставьте diff, получите краткое описание, возможные
риски с цитатами и список проверок. Решение по PR принимает человек.
Спецификации и [общий контракт](../CONTRACT.md) согласованы до кода;
процесс и материалы сдачи — в [отчёте ДЗ 5](../REPORT.md).

## Установка и запуск

Из корня ITMOv2 (Python 3.11+; проверяется на Python 3.13):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r practices/practice_05/project/requirements.lock
make -C practices/practice_05/project run
```

Открыть http://127.0.0.1:8000. Для другого порта добавить `PORT=8001`.
По умолчанию работает явно обозначенный demo-режим. Он выполняет
детерминированные правила на показанных строках; это не вызов AI-модели.
Пример для вставки: [TRAINING_PR.diff](../inputs/TRAINING_PR.diff).
Сервер останавливается Ctrl+C. В diff следует использовать учебные данные.

## Проверки

Из project:

```bash
make test       # unittest логики и HTTP API, без внешней модели
make e2e        # Google Chrome headless + отдельный localhost сервер
make check      # обе группы
make coverage   # дополнительный отчёт покрытия backend
```

E2E использует установленный Google Chrome и отдельный временный профиль.
Альтернатива: установить Chromium через `.venv/bin/python -m playwright install chromium`
из корня ITMOv2 и запустить `PLAYWRIGHT_CHANNEL=chromium make e2e` из project.
Проверки самостоятельно запускают сервер на свободном loopback-порту,
останавливают его и закрывают браузер. Выводы и скриншоты сохраняются в ../evidence.

Основной browser test проходит реальный API/demo. Ошибки сети, некорректный
ответ и позднее завершение отдельно моделируются перехватом browser request;
они проверяют поведение UI, а ошибки backend проверяются отдельными API-тестами.
Проверка DOM/ARIA не является прослушиванием настоящего screen reader.

## Настоящая модель

Адаптер ожидает chat/completions-совместимый JSON-ответ. Настройки — только
в серверном окружении; ключ не вводится в браузер и не попадает в репозиторий.
Из project:

```bash
export REVIEW_MODE=live
export REVIEW_LLM_URL='https://АДРЕС-ПРОВАЙДЕРА/ПОЛНЫЙ-ПУТЬ/chat/completions'
export REVIEW_LLM_MODEL='ИМЯ-МОДЕЛИ'
read -rsp 'API key: ' REVIEW_LLM_KEY; echo
export REVIEW_LLM_KEY
make run
```

После работы: `unset REVIEW_LLM_KEY`. Для возвращения к demo:
`REVIEW_MODE=demo make run`. Если live не настроен, приложение отвечает 503;
скрытой замены live на demo нет. 504 означает общий лимит ожидания 10 секунд.
Невалидные структура или цитата модели дают 502 без частичного результата.

## Чего проверка не гарантирует

Совпадение цитаты с diff не доказывает смысловую правильность замечания.
Нулевой список рисков не гарантирует отсутствие дефектов. Маскирование
покрывает конечный список форматов из согласованной спецификации; неизвестные
форматы не гарантированы. Поддерживаются текстовые unified diff, включая
частичные учебные hunks; binary/combined merge/Git-экранированные пути вне scope.
В частичных diff с несколькими файлами лучше сохранять `diff --git`:
без явной границы пары строк, похожие на заголовки, могут быть неоднозначны.
Данных в истории нет; после перезагрузки страницы начинается новый сеанс.
Это локальный учебный сервис без пользовательских аккаунтов.

## Технические источники

- [Playwright: браузеры и Chrome](https://playwright.dev/python/docs/browsers)
- [Playwright: библиотека Python](https://playwright.dev/python/docs/library)
- [FastAPI: статические файлы](https://fastapi.tiangolo.com/tutorial/static-files/)
