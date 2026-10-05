"""Ask five repo questions to a local Ollama model and save full answers to Markdown.

Usage:
  python3 ask_questions.py --model itmo --output results/resp.md
  python3 ask_questions.py --model itmo-agent --output results/resp_agent.md

This script only uses local files under demo/ as context and does not read _private/.
"""
from __future__ import annotations

import argparse
import json
import textwrap
import urllib.request
from pathlib import Path


def read_questions(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # lines like: "1. Как запустить тесты? ..."
        if line[0].isdigit() and "." in line:
            try:
                _, rest = line.split(".", 1)
            except ValueError:
                continue
            question = rest.strip()
            if question:
                out.append(question)
    return out


def build_context(demo_dir: Path) -> str:
    # Keep context modest but sufficient: README, Makefile, service, tests.
    parts: list[str] = []
    for fname in [
        "README.md",
        "Makefile",
        "service.py",
        "test_service.py",
        "opencode.json",
        "repo-system.txt",
    ]:
        p = demo_dir / fname
        if p.exists():
            parts.append(f"=== {fname} ===\n" + p.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def ask_ollama(model: str, user_content: str, temperature: float = 0.2, num_ctx: int = 4096) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": user_content}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": 768,
        },
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Local Ollama model name, e.g. itmo or itmo-agent")
    ap.add_argument("--output", required=True, help="Path to write Markdown with answers")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    questions = read_questions(root / "QUESTIONS.md")
    ctx = build_context(root / "demo")

    md_lines: list[str] = []
    md_lines.append(f"Model: {args.model}")
    md_lines.append("")
    for i, q in enumerate(questions, start=1):
        # Construct per-question prompt with shared context.
        prompt = textwrap.dedent(
            f"""
            Ниже приведены материалы проекта. Ответь на вопрос кратко по фактам из материалов. Если данных нет, скажи об этом.

            {ctx}

            Вопрос {i}: {q}
            """
        ).strip()
        try:
            answer = ask_ollama(args.model, prompt)
        except Exception as e:
            # Record failure as a section to keep output consistent.
            md_lines.append(f"### Вопрос {i}")
            md_lines.append(f"> {q}")
            md_lines.append("")
            md_lines.append("Ошибка при обращении к локальной модели:")
            md_lines.append(f"```")
            md_lines.append(str(e))
            md_lines.append(f"```")
            md_lines.append("")
            continue

        content = answer.get("message", {}).get("content", "")
        md_lines.append(f"### Вопрос {i}")
        md_lines.append(f"> {q}")
        md_lines.append("")
        md_lines.append("Ответ:")
        md_lines.append("```")
        md_lines.append(content)
        md_lines.append("```")
        md_lines.append("")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    print("Saved:", out_path)


if __name__ == "__main__":
    main()
