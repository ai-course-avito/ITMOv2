Сводка артефактов evidence

- 00-recon.md — разведка репозитория и план.
- 01-agents-md.log — применение правил AGENTS.md: запуск unified check.
- 02-hook-setup.md — настройка onWrite hook; 02-hook-feedback.log — пример срабатывания.
- 03-skill-run.log — запуск skill test-runner, сохранённый лог.
 - 04-mcp-config.md — описание MCP tool; 04-mcp-success.log/04-mcp-error.log — диалоги агента с успешным и ошибочным вызовами.
 - 04-mcp-stdio-success.log/04-mcp-stdio-error.log — raw stdio-вызовы MCP для соответствия спеке.
- 05-feature-a.log — будет добавлен при изменениях A.
- 06-feature-b.log — будет добавлен при worktree B.
- 07-merge-check.log — итоговая проверка после merge, фактический вывод.

- .last-check.log — последняя сырая копия вывода unified check; вспомогательный лог в evidence, может быть пустым.

Примечание по hook: onWrite hook добавлен в opencode.json. В этой среде CLI не инициирует события записи; требуется запущенный OpenCode клиент. Если автозапуск не сработал, см. decisions.md для версии и примечаний.
