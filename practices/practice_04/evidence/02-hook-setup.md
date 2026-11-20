# Hook setup

Цель: автоматически запускать проверки после правок в `practices/practice_04` и возвращать результат агенту.

Интеграция через OpenCode hooks в `opencode.json`:

```
{
  "hooks": {
    "onWrite": [
      {
        "name": "practice_04_check",
        "shell": true,
        "command": "bash practices/practice_04/scripts/check.sh",
        "cwd": ".",
        "patterns": [
          "practices/practice_04/src/**",
          "practices/practice_04/tests/**",
          "practices/practice_04/scripts/**"
        ]
      }
    ]
  }
}
```

Замечание: если OpenCode требует перезапуска для загрузки хуков, попросить пользователя перезапустить клиент и продолжить.
