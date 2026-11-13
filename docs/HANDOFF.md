# Handoff: Практика 4

## Состояние
- Фича A: skill pptx, MCP context7, STYLEGUIDE, make check, pre-commit hook
- Фича B: check_pptx.py, цель check_pptx в Makefile
- Merge B в A выполнен (fast-forward)
- Subagent review: проведён (tester), 2 замечания
- MCP context7: применён для проверки check_pptx.py по документации python-pptx

## Команды проверки
cd practices/practice_03 && make check
- ruff (PEP 8)
- check_pptx.py (exit 0 при >= 5 слайдах)
- unittest (3 теста)

## Ограничения
- check_pptx.py использует XML fallback, если python-pptx недоступен
- MCP context7 использовался при разработке и review, не в runtime

## Что дальше
- Свой MCP tool (домашка)
- Разбор skill pptx (домашка)
- reflection.md (домашка)
