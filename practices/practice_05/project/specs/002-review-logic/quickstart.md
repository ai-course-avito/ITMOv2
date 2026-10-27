# Quickstart: будущая проверка логики и API

Это инструкция для этапа после реализации, не отчёт о выполнении. Контракт и модель данных: [contracts/api.md](contracts/api.md), [data-model.md](data-model.md).

## Предусловия

Рабочий каталог `practices/practice_05/project`; repo-root `.venv` с Python 3.13 и зависимостями requirements.txt, которые ведёт root. Доступная команда Python: `../../../.venv/bin/python`. Нужны созданные app/, tests/ и static/ обеих команд. Ключи в файлы репозитория не записывать.

## Локальная проверка

```bash
../../../.venv/bin/python -m unittest tests.test_logic tests.test_api -v
REVIEW_MODE=demo ../../../.venv/bin/python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Эквивалентные цели root: `make test`, `make run`, `make e2e`, `make check`. Uvicorn access log отключён; собственный журнал приложения содержит только request_id/duration_ms/status.

Открыть http://127.0.0.1:8000, вставить `../inputs/TRAINING_PR.diff`, нажать «Проверить diff». Ожидаются mode demo/видимая пометка «ДЕМО», summary, раздел «Возможные риски» с точными цитатами и хотя бы одна проверка. Это правила демонстрации, не живое AI-ревью.

## Приёмочные сценарии

1. Учебный сокращённый diff принят; каждая цитата находится по пути/координате. Отдельно проверить old line удаления и new line добавления/контекста.
2. 20000/20001 code points, Unicode emoji, LF/CRLF, пустой ввод и неверная форма дают согласованные исходы; при отказе adapter не вызывается.
3. Синтетические секреты из конечного списка исчезают из outbound prompt, результата и журнала; количество строк сохранено. Evidence проверяется после последнего маскирования.
4. Injected adapter: 0/3 риска успешны, 4/неверная цитата/null/RULE-only/лишнее поле дают INVALID_MODEL_OUTPUT без частичного успеха.
5. Injected adapter: задержка, transport error, отмена дают управляемый исход и не запускают повтор/скрытый demo. Production timeout равен 10 секундам; короткий test deadline допустим только через внутреннюю инъекцию и явно отмечается.
6. ASGI API и static routes работают вместе. После UI success/error текст сохраняется/очищается по контракту. Browser e2e ведёт root в tests/test_e2e.py.

## Live

После настройки REVIEW_MODE=live, REVIEW_LLM_URL (полный chat/completions URL), REVIEW_LLM_MODEL и REVIEW_LLM_KEY во внешнем окружении запустить ту же app. Без полного конфига допустимый diff даёт 503 MODEL_NOT_CONFIGURED. Использовать учебный diff без реальных секретов. Успех имеет mode live. Без фактического вызова этот режим не считается проверенным; отказ никогда не заменяется demo-успехом.
