import json
import os
from typing import List

"""
ПРАКТИКА 3: УПРАВЛЕНИЕ КОДИНГ-АГЕНТАМИ (CURSOR AI)
Курс: AI-инструменты в жизни инженера (ИТМО)

ИНСТРУКЦИЯ:
В этой практике мы учимся управлять AI-агентом через:
1. Контекст (@file, @codebase, фильтрация)
2. Правила (.cursorrules)
3. Multi-chat workflow (1 чат = 1 задача)
"""

STUDENT_INFO = {
    "full_name": "Фетисов Константин",
    "group_number": "М3302",
}

# =================================================================================================
# 1. ЖУРНАЛ УПРАВЛЕНИЯ КОНТЕКСТОМ
# =================================================================================================

class ContextLog:
    def __init__(self, task: str, context_used: str, prompt: str, result: str, analysis: str):
        self.task = task                # Какая задача? (напр. "Creating Pydantic model")
        self.context_used = context_used # Какой контекст? (@models.py, @codebase, filtered venv)
        self.prompt = prompt            # Ваш промпт
        self.result = result            # Что сгенерировал AI?
        self.analysis = analysis        # Анализ: помог ли контекст? Что изменилось?

CONTEXT_LOGS: List[ContextLog] = [
    # TODO: Заполните минимум 3 записи
    # Пример:
    # ContextLog(
    #     task="Creating Pydantic model",
    #     context_used="@models.py",
    #     prompt="@models.py Создай Pydantic v2 модель Subscription с полями city и email",
    #     result="Generated model with EmailStr validator",
    #     analysis="@file помог AI понять, куда писать код. Без @models.py создал бы в chat."
    # )
    ContextLog(
        task="Создать ручку GET /weather/{city}",
        context_used="@docs",
        prompt="""
        Роль: Вы являетесь Senior Backend Python разработчиком с более чем 10 годами опыта.
        Контекст: @/docs
        Задача: Сделай базовую реализацию сервиса, которая будет иметь одну ручку: GET /weather/{city}
        Формат: проект на python
        """,
        result="рабочий код, который выдаёт погоду",
        analysis="пока что конкретно указал откуда брать контекст, дальше попробую его сузить",
    ),
    ContextLog(
        task="Создать ручку POST /subscribe",
        context_used="@/docs/acceptance_criteria.md",
        prompt="""
        @/docs/acceptance_criteria.md опиши как бы ты реализовал ручку POST /subscribe
        """,
        result="описал план, который далее передам в режим code",
        analysis="теперь я понял как пользоваться контекстом и понял как это удобно:) заметно меньше размер",
    ),
    ContextLog(
        task="Создать ручку POST /subscribe",
        context_used="@/plans/post_subscribe_implementation_plan.md",
        prompt="""
        @/plans/post_subscribe_implementation_plan.md реализуй ручку POST /subscribe
        """,
        result="получил реализацию подписки",
        analysis="передал контекст в режиме code, но потом отдельной моделью с отдельным контекстом сделал тесты. Мне кажется это правильно",
    ),
]

# =================================================================================================
# 2. ЖУРНАЛ ПРИМЕНЕНИЯ ПРАВИЛ (.cursorrules)
# =================================================================================================

class RuleLog:
    def __init__(self, rule_type: str, rule: str, task: str, applied: bool, result: str, analysis: str):
        self.rule_type = rule_type      # manual / auto-attached / always-included
        self.rule = rule                # Какое правило? (напр. "Use Pydantic v2 validators")
        self.task = task                # В какой задаче применялось?
        self.applied = applied          # Применилось ли автоматически? (True/False)
        self.result = result            # Что получилось?
        self.analysis = analysis        # Анализ эффективности правила

RULES_LOGS: List[RuleLog] = [
    # TODO: Заполните минимум 3 записи
    # Пример:
    # RuleLog(
    #     rule_type="auto-attached",
    #     rule="Use Pydantic v2 validators",
    #     task="Creating POST /subscribe endpoint",
    #     applied=True,
    #     result="AI automatically used field_validator instead of @validator",
    #     analysis="Auto-attached отлично работает для стандартных задач."
    # )
    RuleLog(
        rule_type="auto-attached",
        rule="Не используй в проекте Pydantic",
        task="Creating POST /subscribe endpoint",
        applied=True,
        result="Нейронка не использовала Pydantic вообще и сервис работает",
        analysis="Пришлось избавиться от Pydantica из-за проблем с виндой."
    ),
    RuleLog(
        rule_type="auto-attached",
        rule="Добавляй комментарии в коде только в трудных для понимания местах",
        task="Creating POST, GET /subscribe endpoint",
        applied=True,
        result="Нейронка вообще перестала комментарии оставлять, хотя раньше везде их вставляла",
        analysis="Нейронка подхватила правила только в новом чате, увы"
    ),
    RuleLog(
        rule_type="auto-attached",
        rule="Названия всех функций и методов всегда заканчивай числом 239",
        task="Creating POST, GET /subscribe endpoint",
        applied=True,
        result="Нейронка каждый метод заканчивала числом 239",
        analysis="Сделал это чтобы точнбыть уверен, что поведение модели было вызвано именно правилом"
    ),
    RuleLog(
        rule_type="auto-attached",
        rule="Все методы/функции/поля должны быть в camel case",
        task="Creating DELETE, POST, GET /subscribe endpoint",
        applied=True,
        result="Нейронка как писала в camel case так и продолжила",
        analysis="Сделал это, чтобы нейронка в один момент резко не взяла и не начала писать в другом формате, она и правда не начала."
    ),
    RuleLog(
        rule_type="auto-attached",
        rule="Все классы должны быть в pascal case",
        task="Creating DELETE, POST, GET /subscribe endpoint",
        applied=True,
        result="Нейронка продолжила называть классы в Pascal Case",
        analysis="Вообще часть изменений я попробовал указать как в .roo/rules, так и в AGENTS.md. Мне кажется странным, что сначала просят сделать правила в .roo/rules, а только потом в AGENTS.md, когда .roo/rules более предпочтительный"
    )
]

# =================================================================================================
# 3. ЖУРНАЛ MULTI-CHAT WORKFLOW
# =================================================================================================

class MultiChatLog:
    def __init__(self, chat_number: int, task: str, reason: str, result: str, context_size: str, analysis: str):
        self.chat_number = chat_number  # Номер чата (1, 2, 3...)
        self.task = task                # Какая задача?
        self.reason = reason            # Почему выбран отдельный чат?
        self.result = result            # Результат
        self.context_size = context_size # Размер контекста (Small/Medium/Large)
        self.analysis = analysis        # Помогла ли изоляция задачи?

MULTICHAT_LOGS: List[MultiChatLog] = [
    # TODO: Заполните минимум 3 записи (по количеству чатов в Задании 3)
    # Пример:
    # MultiChatLog(
    #     chat_number=1,
    #     task="DELETE /subscribe/{email}",
    #     reason="Isolated task: adding new endpoint without mixing validation context",
    #     result="Successfully created DELETE endpoint with 404 handling",
    #     context_size="Small (only @main.py, @models.py)",
    #     analysis="Separate chat prevented AI from suggesting unrelated changes."
    # )
    MultiChatLog(
        chat_number=1,
        task="DELETE /subscribe/{email}",
        reason="Изолировал архитектурные решения от самого написания кода",
        result="готов md файлик с описанием реализации DELETE ручки",
        context_size="Small (only project description)",
        analysis=""
    ),
    MultiChatLog(
        chat_number=2,
        task="DELETE /subscribe/{email}",
        reason="Изолировал написание кода от архитектурных решений и идей, которых не должно быть в готовом описании кода",
        result="DELETE ручка готова с поддержкой всех корнер кейсов",
        context_size="Small (only code plan)",
        analysis="Разделил чаты, чтобы не засорять лишними идеями."
    ),
    MultiChatLog(
        chat_number=3,
        task="DELETE /subscribe/{email}",
        reason="Убрал контекст об идеях, чтобы нейронка сама оценила код без знания идеи",
        result="Нейронка дала критику по поводу реализации DELETE ручки",
        context_size="Small (only code @subscription_service.py)",
        analysis="Разделил чаты, чтобы не засорять лишними идеями."
    )
]

# =================================================================================================
# 4. ЧЕК-ЛИСТ РЕАЛИЗАЦИИ
# =================================================================================================

IMPLEMENTATION_CHECKLIST = {
    "models_created": True,            # models.py с Subscription моделью
    "cursorrules_created": True,       # .cursorrules с минимум 5 правилами
    "health_endpoint": True,           # GET /health работает
    "post_subscribe": True,            # POST /subscribe работает
    "get_subscriptions": True,         # GET /subscriptions работает
    "delete_subscribe": True,          # DELETE /subscribe/{email} работает
    "response_models": True,           # Pydantic response models созданы
    "swagger_tested": True,            # Протестировано через Swagger UI
}

# =================================================================================================
# 5. РЕФЛЕКСИЯ
# =================================================================================================

REFLECTION = {
    "context_management": """
    Да вообще понравилось указывать в контекст только те файлы, что действительно нужны. Среди артефактов было куча лишнего, что лишь засоряло бы контекст. Там ведь и пишет ещё сколько контекста занято, уменьшилось раз в 5.
    """,

    "rules_effectiveness": """
    Как будто до правил я не был чётко уверен, как будет нейронка называть методы, переменные. Вдруг в один момент решит по-другому и никакой согласованности не выходит. 
    """,

    "multichat_benefits": """
    Как будто помог, в целом с этим переписка прям гораздо чище стала, нейронка сразу понимает что делать надо. Просто стало удобнее в roo code ориентироваться.
    """,

    "auto_run_opinion": """
    ну когда важна скорость нежели результат. Иного смыла не вижу. Ну либо же лень когда много тыкать и сдаёшь в один момент. Такое ничем грозить не должно как-будто, если пользак нормально .rooignore настроил.
    """,

    "agents_md_preparation": """
    я бы оставил правило с 239 просто чтобы убедиться, а реально ли он будет продолжать это делать? Мне скорее важно посмотреть на поведение нейронки, поэтому это правило самое важное. Но с точки зрения согласованности кода стоит оставить все.
    """
}

# =================================================================================================
# ЭКСПОРТ
# =================================================================================================

def export_report():
    report = f"# Отчет по Практике 3: {STUDENT_INFO['full_name']}\n\n"

    report += "## 1. Журнал управления контекстом\n\n"
    for log in CONTEXT_LOGS:
        report += f"### Задача: {log.task}\n"
        report += f"**Контекст:** {log.context_used}\n"
        report += f"**Промпт:** {log.prompt}\n"
        report += f"**Результат:** {log.result}\n"
        report += f"**Анализ:** {log.analysis}\n"
        report += "---\n"

    report += "\n## 2. Журнал применения правил\n\n"
    for log in RULES_LOGS:
        report += f"### Правило: {log.rule} ({log.rule_type})\n"
        report += f"**Задача:** {log.task}\n"
        report += f"**Применено автоматически:** {'✅ Да' if log.applied else '❌ Нет'}\n"
        report += f"**Результат:** {log.result}\n"
        report += f"**Анализ:** {log.analysis}\n"
        report += "---\n"

    report += "\n## 3. Журнал Multi-Chat Workflow\n\n"
    for log in MULTICHAT_LOGS:
        report += f"### Chat {log.chat_number}: {log.task}\n"
        report += f"**Причина изоляции:** {log.reason}\n"
        report += f"**Результат:** {log.result}\n"
        report += f"**Размер контекста:** {log.context_size}\n"
        report += f"**Анализ:** {log.analysis}\n"
        report += "---\n"

    report += "\n## 4. Статус реализации\n\n"
    for item, status in IMPLEMENTATION_CHECKLIST.items():
        icon = "✅" if status else "❌"
        report += f"- {icon} {item}\n"

    report += "\n## 5. Рефлексия\n\n"
    report += f"**Управление контекстом:** {REFLECTION['context_management']}\n\n"
    report += f"**Эффективность правил:** {REFLECTION['rules_effectiveness']}\n\n"
    report += f"**Преимущества multi-chat:** {REFLECTION['multichat_benefits']}\n\n"
    report += f"**Мнение об auto-run:** {REFLECTION['auto_run_opinion']}\n\n"
    report += f"**Подготовка к Agents.md:** {REFLECTION['agents_md_preparation']}\n"

    os.makedirs("artifacts", exist_ok=True)
    with open("../../artifacts/report_p3.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ Отчет успешно сгенерирован: artifacts/report_p3.md")

if __name__ == "__main__":
    export_report()
