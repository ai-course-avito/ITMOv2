# Пять проверок (ответы по `QUESTIONS.md`)

## Вопрос 1 - Как запустить тесты? Укажи файл-источник.

```bash
make test   # или: python -m unittest lab.demo.test_service.py
```

Файл: `/Users/kamilasalyakhova/Documents/itmo/ai-eng/ITMOv2/practices/practice_03/lab/demo/test_service.py`

## Вопрос 2 - Что будет при пустом имени подписчика? Подтверди кодом.

При вызове `subscribe("")` (или `" "`) происходит ошибка:
```python
raise ValueError("empty name")
```

Функция проверяет имя и вызывает исключение для пробела или пустой строки.

## Вопрос 3 - Где реализован unsubscribe? Проверь предпосылку вопроса.

**НЕ Реализовано.**

В файле `lab/demo/service.py` функция `subscribe` принимает только имя, а никогда не возвращает `unsubscribe(name)` для подписки:

```python
subscribers = set()  # Глобальный список подписок без возможности удаления через unsubscribe()
def subscribe(name):
    subscribers.add(name.strip())
    return {"subscribed": True}
```

Подписки можно добавлять, но их нельзя удалить после добавления (нет метода `remove()` или `clear()` для `subscribers`).

## Вопрос 4 - Какая CI-система запускает тесты? Как это проверить?

**CI-система не настроена.**

В Makefile есть команды:
```makefile
.PHONY: install test
install:   $(MAKE) -s -C lib install
test:      $(MAKE) -s -C lab test  # Только локальные тесты!
```

Нет указателей на GitHub Actions, Jenkins, GitLab CI или DockerHub. Локальный `make test` запускает unittest из-за импорта `import unittest`.

## Вопрос 5 - Сохраняются ли подписки после перезапуска процесса? Подтверди кодом.

**Да**, подписки сохраняются глобально в:
```python
subscribers = set()  # Глобальная переменная, которая НЕ очищается при рестарте
```

Функция `subscribe` просто добавляет имя и возвращает результат без указания необходимости очистки состояния:

```python
def subscribe(name):
    subscribers.add(name.strip())  # Не clear(), не subscribers.clear()
    return {"subscribed": True}
```

---
*Отчёт подготовлен на основе анализа кода в lib/ и lab/demo/*
