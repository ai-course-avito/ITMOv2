# План общей интеграции ДЗ 5

Основание: CONTRACT.md v1.0 и одобрение пользователя 2026-10-27.
Команды готовят и реализуют собственные plan/tasks через Spec Kit;
общая сборка и браузерные проверки выполняются после объединения частей.

- [x] I01 Сохранить согласованные спецификации «после» и commit до прикладного кода.
- [x] I02 Создать project/requirements.txt, requirements-dev.txt и Makefile.
- [x] I03 Связать GET /, static assets и POST /api/reviews; проверить отсутствие дрейфа контракта.
- [x] I04 Создать project/tests/test_e2e.py: браузер → реальный HTTP → demo-логика → UI.
- [x] I05 Проверить через браузер success, empty/20000/20001, invalid diff, ошибку сервера,
  loading/double submit, сетевую ошибку, форму результата, literal rendering,
  очистку, keyboard/focus, ширину 360px и поздний ответ после 15 секунд.
- [x] I06 Запустить unit/API и E2E; сохранить вывод и скриншоты, визуально проверить экран.
- [x] I07 Применить speckit-converge к обеим feature directories, устранить реальные пробелы.
- [x] I08 Обновить отчёт, сравнение фреймворков, журнал и commit.
- [x] I09 Записать личную рефлексию.

Окружение: Python 3.13, FastAPI 0.162.0, HTTPX 0.28.1, Uvicorn 0.54.0;
Playwright с локальным Google Chrome (headless), без внешних сайтов.
Для E2E сервер запускается отдельным процессом на свободном loopback-порту
и останавливается в cleanup. Контролируемые browser route responses применяются
только к проверкам UI ошибок/неверного результата; happy path проходит реальный
backend с явной demo-моделью. Эти разные виды доказательств отмечены в validation.md.

Официальные источники, проверенные при подготовке:
- https://playwright.dev/python/docs/library
- https://playwright.dev/python/docs/browsers
- https://playwright.dev/python/docs/screenshots
- https://fastapi.tiangolo.com/tutorial/static-files/
