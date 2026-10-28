# MCP Tool: file-summary

Идея: предоставить локальный инструмент инспекции файла: `file_summary(path)`.

Описание tool:
- Имя: `file_summary`
- Аргументы: `path` (string, обязательный)
- Результат: объект `{ path, size_bytes, line_count, sha256 }`
- Ошибки: `Method not found`, `File not found`, `invalid params` (jsonrpc error code -32602)

Зачем: позволяет агенту быстро получать сводку по артефактам (логи evidence, скрипты), не читая файл целиком.

Подключение MCP:
- Сервер: `practices/practice_04/mcp/file_summary_server.py`
- Конфиг: в `opencode.json` в секции `mcpServers` или `mcp` (в зависимости от версии клиента)

Проверка в Inspector:
- Успех: валидный путь к файлу (`practices/practice_04/scripts/check.sh`)
- Ошибка: несуществующий путь или неверный тип аргумента
