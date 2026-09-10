# Юнит-тесты

## Тест-кейсы

| ID | Назначение | Предусловия | Действие | Ожидаемый результат | Evidence |
|---|---|---|---|---|---|
| U1 | ReviewService вызывает LLM.generate с промптом | Мок LLM.generate возвращает "ok" | Вызвать review(diff="diff --git a b") | Возвращён результат, содержащий комментарий; LLM.generate вызван с prompt, включающим diff | TRAINING_PR.diff: app/review_service.py:19-22 |
| U2 | Функция create_review падает при отсутствии ключа diff (текущее поведение) | Импортирован обработчик `create_review`; подставлен заглушечный review_service | Вызвать create_review(payload={}) напрямую | Исключение KeyError | TRAINING_PR.diff: app/api.py:36-37 |

## Как использовали AI

- Для систематизации тестов по функциональным блокам; запись P1-03 в prompts.md.
