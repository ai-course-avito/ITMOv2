#!/bin/sh
# Fail-first проверка: запускает ОДИН новый тест и решает, упал ли он по правильной причине.
# Использование: sh .claude/skills/tdd-feature/scripts/fail_first.sh tests/test_x.py
#                sh .claude/skills/tdd-feature/scripts/fail_first.sh "tests/test_x.py::test_name"
# Последняя строка вывода: "FAIL-FIRST OK: ..." (exit 0) или "FAIL-FIRST BAD: ..." (exit 1).
# OK только если тест упал на assertion/исключении ВНУТРИ теста (pytest: FAILED).
# BAD: тест прошел, нет тестов, ошибка сбора (SyntaxError/ImportError), ошибка setup/фикстуры.

if [ -z "$1" ]; then
    echo "FAIL-FIRST BAD: не указан тест (путь к файлу или node id)"
    exit 1
fi

cd "$(dirname "$0")/../../../.." || { echo "FAIL-FIRST BAD: не найден корень проекта"; exit 1; }

if [ -n "$PYTHON" ]; then
    PY="$PYTHON"
elif [ -x ".venv/Scripts/python.exe" ]; then
    PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    PY="python"
fi

out=$("$PY" -m pytest "$@" -q -x --tb=short -p no:cacheprovider -rfE 2>&1)
code=$?
printf '%s\n' "$out" | tail -n 30

# Первая "понятная" причина: строка "E   ..." из traceback или строка FAILED
reason=$(printf '%s\n' "$out" | grep -E '^E  ' | head -n 1 | sed 's/^E *//')
[ -z "$reason" ] && reason=$(printf '%s\n' "$out" | grep -E '^(FAILED|ERROR) ' | head -n 1)

echo "-----"
case "$code" in
    0)
        echo "FAIL-FIRST BAD: тест прошел сразу. Либо фича уже есть, либо тест ничего не проверяет."
        exit 1 ;;
    1)
        if printf '%s\n' "$out" | grep -qE '^FAILED '; then
            echo "FAIL-FIRST OK: тест упал внутри теста. Причина: $reason"
            echo "Проверь глазами: причина должна быть 'нет нужного поведения' (например 404 вместо 422), а не опечатка в тесте."
            exit 0
        fi
        echo "FAIL-FIRST BAD: ошибка setup/фикстуры, а не assertion. $reason"
        exit 1 ;;
    2)
        echo "FAIL-FIRST BAD: ошибка сбора тестов (SyntaxError/ImportError/прерывание). $reason"
        exit 1 ;;
    5)
        echo "FAIL-FIRST BAD: ни один тест не найден (проверь путь и имя test_*)."
        exit 1 ;;
    *)
        echo "FAIL-FIRST BAD: pytest завершился с кодом $code (неверные аргументы или внутренняя ошибка). $reason"
        exit 1 ;;
esac
