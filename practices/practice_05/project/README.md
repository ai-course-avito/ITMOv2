# Простенький менеджер задач

Мини-проект: Flask-бэкенд + HTML/CSS/JS фронтенд, хранение задач в `tasks.json`.

Запуск локально (Linux/macOS):

1. Перейдите в каталог проекта: `cd practices/practice_05/project`
2. Установите зависимости в отдельное виртуальное окружение:
   - `make install`
3. Запустите сервер:
   - `make run`

Приложение будет доступно по адресу: `http://127.0.0.1:5000/`

API:
- GET `/api/tasks` — список задач
- POST `/api/tasks` — создать задачу `{ title: string }`
- PATCH `/api/tasks/<id>` — обновить флаги/название `{ done?: boolean, title?: string }`
- DELETE `/api/tasks/<id>` — удалить задачу
