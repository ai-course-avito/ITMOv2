# Итог проверок ДЗ 5

Дата: 2026-10-27. Ветка: practice_05. Python 3.13, Google Chrome headless.

| Проверка | Фактический результат | Артефакт |
|---|---|---|
| Итоговый make check | 42 unit/API + 11 browser tests, все PASS | final-check.txt |
| Покрытие backend с ветвлениями | 94%; модуль маскирования 100% | logic-coverage.txt |
| Дополнительное ревью | Ошибки воспроизведены и исправлены | review-findings.md, audit-regression-red.txt, audit-regression-green.txt |
| UI desktop/mobile/error | Скриншоты просмотрены; на 360px нет overflow | ui-desktop.png, ui-mobile.png, ui-error.png |
| Повторная сверка Spec Kit | Незакрытых расхождений не найдено | audit-convergence.md |
| Снимки before/after | Все 12 SHA256 совпали, согласованные specs неизменны | audit-integrity.json |
| Решение до реализации | В commit 5301bc5 есть agreed specs, app/ и static/ отсутствуют | audit-integrity.json |
| Условия курса | Исходные README и PDF не изменены | audit-integrity.json |

final-check.txt и logic-coverage.txt относятся к текущему коду после аудита.
Более ранние e2e.txt, logic-green.txt и первоначальные converge-отчёты сохраняют
результаты соответствующих этапов; их числа не являются текущим итогом.

Реальный browser → localhost API → demo adapter → UI проверен на учебном diff,
ошибочном вводе, ручном повторе, ровно 20000 Unicode code points и дополнительном
случае привязки результата к файлу. Пустой ввод и 20001 символ отклоняются до
запроса. Сеть, provider error, malformed success, late response и live-label
проверяются управляемыми browser responses. Ожидание UI в 15 секунд проверяется
реальным таймером. Backend отдельно проверяет таймаут/отмену, формат live-запроса,
структуру ответа, цитаты, маскирование и минимальный журнал.

Ограничения доказательств: внешняя модель в ДЗ 5 не вызывалась, качество её
рекомендаций не измерялось. Screen reader не прослушивался, реальный browser zoom
не менялся: проверены DOM/ARIA, клавиатура и эквивалентная ширина reflow.
Совпадение цитаты не доказывает правильность риска. Ручной успешный demo-сценарий
подтверждён скриншотами; ручной сценарий ошибки отдельно не подтверждён, но
воспроизведён браузерным тестом. Личная рефлексия записана в REFLECTION.md.
