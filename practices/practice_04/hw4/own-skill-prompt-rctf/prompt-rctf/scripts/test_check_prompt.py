import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from check_prompt import check, parse_blocks  # noqa: E402

SCRIPT = Path(__file__).with_name("check_prompt.py")

GOOD = """
Role: Преподаватель баз данных.

Context: Я студент, знаю SQL на уровне SELECT с JOIN, схемы не проектировал.
Готовлюсь к экзамену, нормализацию раньше не изучал.

Task: Объясни первые три нормальные формы на сквозном примере таблицы заказов.

Format:
- Три раздела, по одному на форму.
- В каждом: таблица до, проблема, таблица после.
- До 500 слов, без вступления.
"""


def levels(text, block=None):
    return [(lvl, blk, msg) for lvl, blk, msg in check(text) if block in (None, blk)]


def messages(text, block=None):
    return " ".join(msg for _, _, msg in levels(text, block))


def test_good_prompt_has_no_issues():
    assert check(GOOD) == []


def test_parse_blocks_reads_all_four():
    assert set(parse_blocks(GOOD)) == {"Role", "Context", "Task", "Format"}


@pytest.mark.parametrize("heading", ["## Context:", "**Context:**", "- Контекст:", "Context :"])
def test_headers_are_recognised_in_different_styles(heading):
    text = f"{heading} Факты про проект и ограничения по срокам, инструментам и объёму."
    assert "Context" in parse_blocks(text)


@pytest.mark.parametrize("missing", ["Context", "Task", "Format"])
def test_missing_required_block_is_an_error(missing):
    text = "\n".join(
        line for line in GOOD.splitlines() if not line.startswith(f"{missing}:")
    )
    assert ("ERROR", missing, "блок отсутствует") in check(text)


def test_missing_role_is_only_a_warning():
    text = GOOD.replace("Role: Преподаватель баз данных.", "")
    assert all(lvl == "WARN" for lvl, _, _ in check(text))


def test_empty_block_is_an_error():
    text = GOOD.replace("Task: Объясни первые три нормальные формы на сквозном примере таблицы заказов.", "Task:")
    assert ("ERROR", "Task", "блок пустой") in check(text)


def test_format_without_concrete_structure_is_an_error():
    text = GOOD.replace(
        "Format:\n- Три раздела, по одному на форму.\n- В каждом: таблица до, проблема, таблица после.\n- До 500 слов, без вступления.",
        "Format: Ответь развёрнуто.",
    )
    assert any(lvl == "ERROR" and blk == "Format" for lvl, blk, _ in check(text))


@pytest.mark.parametrize("vague", ["качественно", "подробно", "максимально", "идеально"])
def test_vague_words_are_flagged(vague):
    text = GOOD.replace("До 500 слов, без вступления.", f"До 500 слов, {vague} раскрой тему.")
    assert vague[:7] in messages(text)


@pytest.mark.parametrize(
    "role",
    [
        "Ты гениальный преподаватель.",
        "Ты лучший эксперт по базам данных.",
        "Ты специалист мирового уровня.",
        "Преподаватель с 20-летним опытом.",
    ],
)
def test_role_puffery_is_flagged(role):
    text = GOOD.replace("Role: Преподаватель баз данных.", f"Role: {role}")
    assert levels(text, "Role"), f"не поймано украшение в роли: {role}"


def test_long_role_is_flagged():
    text = GOOD.replace("Role: Преподаватель баз данных.", "Role: " + "преподаватель, " * 30)
    assert "слишком длинная" in messages(text, "Role")


def test_multiple_actions_in_task_are_flagged():
    text = GOOD.replace(
        "Task: Объясни первые три нормальные формы на сквозном примере таблицы заказов.",
        "Task: Объясни нормальные формы, а также приведи примеры и проверь мой код.",
    )
    assert "несколько действий" in messages(text, "Task") or "перечисление" in messages(text, "Task")


def test_indirect_task_start_is_flagged():
    text = GOOD.replace(
        "Task: Объясни первые три нормальные формы на сквозном примере таблицы заказов.",
        "Task: Мне нужно понять нормальные формы на примере таблицы заказов.",
    )
    assert "глагол" in messages(text, "Task")


def test_thin_context_is_flagged():
    text = GOOD.replace(
        "Context: Я студент, знаю SQL на уровне SELECT с JOIN, схемы не проектировал.\nГотовлюсь к экзамену, нормализацию раньше не изучал.",
        "Context: Учусь.",
    )
    assert "короткий" in messages(text, "Context")


def test_context_repeating_task_is_flagged():
    text = GOOD.replace(
        "Context: Я студент, знаю SQL на уровне SELECT с JOIN, схемы не проектировал.\nГотовлюсь к экзамену, нормализацию раньше не изучал.",
        "Context: Объясни первые три нормальные формы на сквозном примере таблицы заказов.",
    )
    assert "повторяет Task" in messages(text, "Context")


def test_leftover_placeholder_is_an_error():
    text = GOOD + "\nTODO дописать пример\n"
    assert any(lvl == "ERROR" and "незаполненный" in msg for lvl, _, msg in check(text))


def run(args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True,
    )


def test_cli_accepts_stdin_and_exits_zero_on_good_prompt():
    result = run(["-"], stdin=GOOD)
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_exits_one_on_error(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text("Task: Сделай хорошо.\n", encoding="utf-8")
    result = run([str(path)])
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_cli_warnings_only_still_exit_zero():
    text = GOOD.replace("Role: Преподаватель баз данных.", "Role: Ты лучший преподаватель.")
    result = run(["-"], stdin=text)
    assert result.returncode == 0
    assert "WARN" in result.stdout


def test_cli_reports_unreadable_file():
    result = run(["/no/such/file.md"])
    assert result.returncode == 2
