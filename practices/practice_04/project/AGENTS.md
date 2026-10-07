# Правила проекта

Контракт: docs/requirements.md
Дизайн: docs/design.md
Пример теста: tests/test_example.py
Проверка: sh scripts/check.sh

Не меняй docs/requirements.md, docs/design.md и scripts/check.sh без явного поручения.
Перед изменением кода прочитай docs/requirements.md, docs/design.md и tests/test_example.py.
Автопроверка подключена как git pre-commit hook: один раз выполните `git config core.hooksPath .githooks` из корня репозитория.
