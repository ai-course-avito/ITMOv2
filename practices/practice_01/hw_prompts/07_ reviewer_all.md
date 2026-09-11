# P1-09. Финальное ревью и точечные правки всех артефактов

**Для файлов:** все артефакты Практики 1 (`practices/practice_01/*.md` + `slides/`)

## Промпт

```text
Роль: senior code/artifact reviewer. Читай practices/practice_01/*.md, TRAINING_PR.diff, CASE.md, README.md, Makefile. НЕ менять TRAINING_PR.diff, CASE.md, README.md, Makefile.

Задача: пройти все 11 артефактов Практики 1 и вернуть точечные правки, где содержимое:
1) не соответствует правилам SEC-1/API-1/REL-1/OUT-1/SCOPE-1/QA-1/OBS-1;
2) остаётся шаблонной заглушкой (пустые ячейки, TEMPLATE-плейсхолдеры, dateFormat не `YYYY-MM-DD`);
3) не привязано к строкам TRAINING_PR.diff (evidence file:line);
4) ломает якоря `make test`.

Формат вывода: для каждого файла — `File: <path>` и список правок `— строка/раздел: что было → что стало (обоснование правилом или строкой diff)`. Только диффабельные изменения, без Chain of Thought.

Definition of Done: `make test` в practices/practice_01/ зелёный; каждый пункт правки ссылается на правило или строку diff; неизменяемые файлы не тронуты.
```
