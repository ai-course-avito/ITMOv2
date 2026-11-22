"""Запустить OpenCode в проекте review-api и сохранить подтверждения.

Каждый вызов — новая сессия `opencode run`. Сырые события сохраняются
в evidence/<name>.jsonl, читаемый протокол с вызовами инструментов и их
выводом — в evidence/<name>.md. Только стандартная библиотека.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

PRACTICE = Path(__file__).resolve().parent.parent
PROJECT = PRACTICE / "review-api"
EVIDENCE = PRACTICE / "evidence"


def short(value, limit):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f" … (+{len(text) - limit} симв.)"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("prompt")
    p.add_argument("--name", required=True)
    p.add_argument("--model", default="opencode/big-pickle")
    p.add_argument("--timeout", type=int, default=1200)
    args = p.parse_args()

    EVIDENCE.mkdir(exist_ok=True)
    cmd = ["opencode", "run", "--model", args.model, "--format", "json", "--", args.prompt]
    env = dict(os.environ, PWD=str(PROJECT))  # OpenCode определяет проект по PWD
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=PROJECT, env=env, capture_output=True, text=True,
                          timeout=args.timeout, stdin=subprocess.DEVNULL)
    seconds = time.perf_counter() - started
    (EVIDENCE / f"{args.name}.jsonl").write_text(proc.stdout, encoding="utf-8")

    lines = [f"# {args.name}", "",
             f"- Модель: `{args.model}`, новая сессия `opencode run` в `review-api/`",
             f"- Время: {seconds:.0f} с, код выхода {proc.returncode}", "",
             "## Запрос", "", "```text", args.prompt, "```", "", "## Ход работы", ""]
    step = 0
    for raw in proc.stdout.splitlines():
        if not raw.startswith("{"):
            continue
        event = json.loads(raw)
        part = event.get("part", {})
        if event.get("type") == "tool_use":
            step += 1
            state = part.get("state", {})
            lines += [f"### {step}. `{part.get('tool')}` → {state.get('status')}", "",
                      "Вход:", "", "```json", short(state.get("input"), 600), "```", ""]
            out = state.get("output") or state.get("error") or ""
            if out:
                lines += ["Результат:", "", "```text", short(out.strip(), 1800), "```", ""]
        elif event.get("type") == "text" and part.get("text", "").strip():
            lines += [part["text"].strip(), ""]
        elif event.get("type") == "error":
            lines += ["**Ошибка:** " + short(event.get("error"), 600), ""]
    if proc.returncode != 0 and proc.stderr.strip():
        lines += ["## stderr", "", "```text", proc.stderr[-1500:], "```"]
    (EVIDENCE / f"{args.name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
