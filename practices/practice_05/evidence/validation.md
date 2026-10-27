# Итог проверок ДЗ 5

Дата: 2026-10-27. Ветка: practice_05. Python 3.13, Google Chrome headless.

| Проверка | Фактический результат | Артефакт |
|---|---|---|
| Финальный make check | 37 unit/API + 10 browser tests, все PASS | final-check.txt |
| Покрытие backend с ветвлениями | 94%; маскирование секретов 100% | logic-coverage.txt |
| Три дефекта при ревью | Исправлены, регрессии RED → GREEN | review-findings.md, logic-*-red.txt, logic-green.txt |
| UI desktop/mobile/error | Визуально просмотрены, 360px без overflow | ui-desktop.png, ui-mobile.png, ui-error.png |
| Spec Kit converge | Обе команды: 0 незакрытых расхождений | ui-convergence.md, logic-convergence.md |
| Снимки before/after | Все 12 SHA256 совпали | before/sha256.json, after/sha256.json |

В последнем общем прогоне unit/API заняли 0.078 s, браузерные — 18.744 s.
e2e.txt сохраняет предыдущий успешный browser run (до последнего исправления
parser); final-check.txt относится к итоговому коду.

Реальный browser → localhost API → demo adapter → UI проверен на учебном diff,
ошибочном вводе, ручном повторе и ровно 20000 Unicode code points. Пустой ввод
и 20001 символ отклоняются до запроса. Сеть, provider error, malformed success,
late response и маркировка live проверяются управляемыми browser responses.
Ожидание UI в 15 секунд проверяется реальным таймером. Backend отдельно проверяет
таймаут/отмену, формат live-запроса, строгую структуру ответа, цитаты, маскирование
и безопасный audit log.

Ограничения доказательств: реального вызова внешней модели и оценки качества её
ревью нет; screen reader не прослушивался, реальный browser zoom не менялся
(проверены DOM/ARIA, клавиатура и эквивалентная ширина reflow). Совпадение цитаты
не доказывает правильность риска. Пользователь предоставил два скриншота успешного
demo-сценария: три риска с цитатами и список проверок. Личная рефлексия записана
по выбранным пользователем формулировкам; ручной сценарий ошибки пока не подтверждён.
