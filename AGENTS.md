# AGENTS: маршрут и правила для AI-агентов

Цель этапа 2: указать агентам минимальный маршрут чтения, границы изменений и условие приёмки A. Правила опираются на материалы практики 3 и структуру этого репозитория.

## 1. Что читать (минимальный маршрут)

Агент сначала читает эти файлы и строит ответы только на их основе:

- practices/practice_03/README.md — как работать на практике 3
- practices/practice_03/PRACTICE.md — сценарий шагов и команды
- practices/practice_03/HOMEWORK.md — требования к домашке и артефактам
- practices/practice_03/TROUBLESHOOTING.md — диагностика
- practices/practice_03/REPORT.md — отчёт по фактическим результатам
- practices/practice_03/lab/QUESTIONS.md — список вопросов для проверки
- practices/practice_03/lab/system.txt — system-инструкция для API-экспериментов
- practices/practice_03/lab/Modelfile — профиль itmo-local
- practices/practice_03/lab/Modelfile.agent — профиль itmo-agent (64k)
- practices/practice_03/lab/Makefile — install/test для учебного кода
- practices/practice_03/Makefile — прокидывает install/test в lab
- practices/practice_03/lab/demo/opencode.json — конфиг тестируемого помощника
- practices/practice_03/lab/demo/repo-system.txt — инструкции тестируемого помощника (read-only)

Дополнительно по проекту:

- practices/practice_01/adr.md — ADR-рыба (при наличии контекста из практик 1–2)

Если файл отсутствует или пуст, агент явно фиксирует это и не подменяет данными «по памяти».

## 2. Команды запуска и проверки

Запуск и проверки выполняет Build-агент из корня форка или из каталога lab, как указано:

- make -C practices/practice_03/lab install — проверка Python 3.10+
- make -C practices/practice_03/lab test — юнит-тесты demo/service.py
- Из lab/:
  - mkdir -p results
  - ollama create itmo-local -f Modelfile
  - python3 experiment.py --mode baseline --output results/baseline.json
  - python3 experiment.py --mode system   --output results/system.json
  - Варианты с temperature и seed — см. PRACTICE.md (раздел про «Одна настройка»)
- OpenCode (read-only проверка): см. PRACTICE.md, пример с agent local-guide

Агент записывает фактические выводы команд в results/ и/или REPORT.md. В отчёте не допускаются непроверенные предположения.

## 3. Границы изменений

- Входные файлы учебного проекта для сравнения не менять: practices/practice_03/lab/demo/*
- Разрешено изменять/создавать:
  - practices/practice_03/lab/results/* — результаты экспериментов
  - practices/practice_03/REPORT.md — отчёт (только факты и обсуждённые выводы)
  - practices/practice_03/lab/Modelfile и Modelfile.agent — по согласованию
  - AGENTS.md — настоящий документ
- Нельзя коммитить артефакты исполнения Python: __pycache__/ и *.pyc
- Тестируемый помощник (local-guide) имеет только read/glob/grep; Build-агент может записывать артефакты.
- Подключения — локальные (Ollama/LM Studio); внешние провайдеры отключены для тестовой сессии.

## 4. Условие приёмки A (Verification)

Сдача этапа считается принятой, если агент:

1) Назвал и прочитал применимые файлы из «Что читать» и процитировал ограничения из repo-system.txt.
2) Подтвердил существование команд проверки (install/test) в Makefile’ах:
   - practices/practice_03/lab/Makefile — цели install и test
   - practices/practice_03/lab/demo/Makefile — цель test
3) Сохранил в results/ фактические результаты хотя бы одного API-запуска (baseline или system) из experiment.py.

Формат проверки: JSON/Markdown с перечислением путей, найденных целей make и ссылкой на сохранённые файлы в results/.

## 5. Как загружать инструкции

- Для тестируемого помощника в demo используется repo-system.txt через конфигурацию opencode.json: поле prompt с {file:./repo-system.txt}.
- Build-агент читает инструкции из файлов, перечисленных в этом документе, через инструменты read/glob/grep и приводит ссылки вида file:line.
- Если чтение не удалось: уточнить у заказчика точный путь и поддерживаемый способ загрузки инструкций (например, {file:...} или явный путь в команде).

## 6. Поведение по умолчанию

- Отвечать кратко, по-русски, указывать источники file:line.
- Если сведений в прочитанных файлах нет — явно писать: «В предоставленных материалах нет ответа».
- Не утверждать выполнение команд без фактических логов.

## 7. Быстрый чеклист для агента

- [ ] Прочитал все файлы из «Что читать» и вывел найденные ограничения
- [ ] Нашёл цели make: install/test в lab и test в demo
- [ ] Выполнил одну из команд experiment.py и сохранил results/*
- [ ] Обновил REPORT.md фактами и ссылками на артефакты

### Дополнение: Style Guide

- При работе с Python-файлами в practices/practice_03/ придерживайся правил из practices/practice_03/STYLEGUIDE.md (PEP 8 выжимка: имена функций, импорты, отступы, пробелы). Читай его перед созданием/правкой .py.
