# Разбор skill pptx

## Что это

Skill `pptx` — это набор инструкций и Python-скриптов для работы с файлами 
PowerPoint (.pptx) без ручного редактирования XML. Он умеет три вещи: 
создавать новые презентации через `pptxgenjs`, редактировать существующие 
(распаковка ZIP → правка XML → упаковка) и читать содержимое через `markitdown`.

## Как устроен

Внутри папки skill лежат:
- `SKILL.md` — главный файл с инструкциями, описанием задач и gotchas
- `scripts/thumbnail.py` — генерирует сетку превью всех слайдов для выбора layout
- `scripts/add_slide.py` — дублирует слайды с правильной регистрацией в XML
- `scripts/clean.py` — удаляет неиспользуемые слайды/медиа после правок
- `scripts/office/validate.py` — проверяет схему, relationships, content-types
- `scripts/office/soffice.py` — обёртка над LibreOffice для конвертации в PDF

Основная идея: агент **не пишет XML руками**, а использует готовые скрипты 
плюс правила из `SKILL.md` (например, «не ставь # в hex-цветах» или 
«после writeFile запусти validate.py»).

## Что я сделал

Я использовал skill для генерации `output.pptx` из `output.md` — файла 
с конспектом Практики 3. Skill сгенерировал 8 слайдов с заголовками, 
а затем я проверил результат через `check_pptx.py` (собственный скрипт): 
он открыл .pptx, извлёк заголовки и вернул PASS.

## Что получилось

- `practices/practice_03/output.pptx` — 8 слайдов
- `practices/practice_03/output.md` — исходный конспект
- Проверка через MCP context7: код `check_pptx.py` соответствует 
  документации python-pptx (`shape.has_text_frame`, `shape.text`)
