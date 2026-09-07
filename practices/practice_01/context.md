# Контекст AS IS и Context Pack

## Продукт и команда сейчас

| Вопрос | Ответ | Источник или допущение |
|---|---|---|
| Какой продукт или сервис рассматриваем? | Сервис AI‑ревью PR на FastAPI | TRAINING_PR.diff (app/api.py, app/review_service.py) |
| Кто им пользуется? | Разработчики/CI, отправляющие diff на ревью | Допущение по назначению API |
| Как устроен текущий процесс? | Клиент отправляет diff, сервис формирует промпт и вызывает LLM, возвращает текст комментария | Код ReviewService.review и POST /api/reviews |
| Где возникает задержка или ошибка? | Отсутствует валидация входа и контракт ответа; риски prompt injection; отсутствие пост‑обработки ответа | Анализ TRAINING_PR.diff |
| Какие системы и команды участвуют? | FastAPI‑приложение, провайдер LLM, команда платформы/QA | Допущение |

## Context Pack для первого рабочего сценария

### Факты и правила

- Факт: Добавлен метод ReviewService.review(diff: str), который конкатенирует diff в промпт и возвращает ответ LLM без пост‑обработки. Источник: app/review_service.py:19-22.
- Факт: Добавлен POST /api/reviews, который принимает payload: dict и обращается к payload["diff"], возвращая dict{"comment": str}. Источник: app/api.py:35-38.
- Правило (FastAPI Request Body): использовать Pydantic‑модели для валидации тела запроса; FastAPI возвращает 422 при невалидном входе. Источник: FastAPI docs "Request Body" https://fastapi.tiangolo.com/tutorial/body/
- Правило (FastAPI Response Model): определять response_model, чтобы фиксировать и валидировать схему ответа и документировать OpenAPI. Источник: FastAPI docs "Response Model" https://fastapi.tiangolo.com/tutorial/response-model/
- Правило (LLM безопасность): учитывать prompt injection и небезопасную обработку вывода; задавать ограничения формата ответа и валидировать его. Источник: OWASP Top 10 for LLM Applications (LLM01, LLM10) https://owasp.org/www-project-top-10-for-large-language-model-applications/

### Формат входа и результата

- Вход: TRAINING_PR.diff (патч изменений app/api.py и app/review_service.py).
- Результат: summary изменений; до 3 рисков в формате candidate -> evidence (по правилу) -> check; список проверок.

### Ограничения и запрещённые действия

- Нельзя: approve, merge, редактировать код PR; нельзя придумывать новые правила.
- Нужно: для каждого риска привести evidence и check; если нет evidence по правилам — пропустить.

### Хороший пример

- app/api.py:35-38 — Кандидат: отсутствует валидация тела запроса. Evidence: маршрут принимает dict и обращается к payload["diff"]; нет Pydantic‑модели. Правило: FastAPI Request Body (docs). Check: POST {} на /api/reviews возвращает 500 вместо 422.

### Плохой пример

- «Надо переписать сервис» без ссылок на строки и правила; без воспроизводимой проверки.

### Что пока неизвестно

- Провайдер LLM; требуемый формат ответа для клиентов; нефункциональные ограничения (таймаут, лимит размера diff).

## Как использовали AI

- Для чего: повторное ревью по master prompt; фиксация контекста и правил
- Тип промпта: master prompt
- Строка в [`prompts.md`](prompts.md): P1-02
- Что проверили и исправили сами: соответствие выводов правилам FastAPI/OWASP, наличие evidence и проверок
