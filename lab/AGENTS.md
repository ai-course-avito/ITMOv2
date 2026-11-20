Стек и структура

- Язык: Python 3.x
- Тесты: `unittest`
- Каталог практики: `practices/practice_04`

Команды проверки

- Единая команда: `bash practices/practice_04/scripts/check.sh`
- Внутри: `python -m unittest -q`

Контракты и примеры

- Тесты: `practices/practice_04/tests/`
- Код: `practices/practice_04/src/`

Нельзя менять

- Секреты и конфиги провайдеров в `opencode.json` (кроме настройки hook/MCP)
- Другие практики и каталоги вне `practices/practice_04`

Правило проверки

- После каждой правки запускать `bash practices/practice_04/scripts/check.sh`
- Если проверка падает — исправлять причину в коде, не менять тесты

Git и секреты

- Коммиты атомарные с понятными сообщениями
- Никаких destructive команд без подтверждения
- Не коммитить секреты
