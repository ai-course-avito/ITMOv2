# review-mini

Учебный сервис ревью диффа из практики 4 (перенесён из ветки `practice-04`
как исходное состояние практики 5). Выращен из `Notify Mini`
(`practices/practice_03/lab/demo`): подписки остались как есть, сверху добавлено
ревью кода локальной моделью из практики 3.

- `app/subscribe.py` — унаследованное поведение подписок;
- `app/review.py` — приём диффа и ответ ревью;
- `app/ollama_client.py` — единственная внешняя зависимость, Ollama на
  `localhost:11434`.

Контракт: [`docs/requirements.md`](docs/requirements.md).
Проверка: `sh scripts/check.sh`. Зависимости: стандартная библиотека Python 3.10+.
