"""Run A/B (baseline vs system) on five questions using local Ollama chat API.
Saves per-question results and an aggregate summary with median speeds.
"""
from __future__ import annotations

import json
import statistics
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "demo"

MODEL = "itmo-local"  # built from Modelfile
NUM_CTX = 4096
NUM_PREDICT = 512
TEMPERATURE = 0.2
SEEDS = [42, 43, 44]  # for median speed; warm-up happens implicitly before first


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def api_chat(payload: dict) -> dict:
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)


def run_once(question: str, system: bool, seed: int) -> dict:
    context_parts = []
    for rel in ("demo/README.md", "demo/service.py", "demo/test_service.py"):
        p = (ROOT / rel)
        if p.exists():
            context_parts.append(f"=== {rel} ===\n{read(p)}\n")
    prompt = "".join(context_parts) + f"\nВопрос: {question}\nОтвечай по приведённым файлам."
    messages = []
    if system:
        messages.append({"role": "system", "content": read(ROOT / "system.txt")})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": TEMPERATURE,
            "seed": seed,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
    }
    started = time.perf_counter()
    out = api_chat(payload)
    record = {
        "request": payload,
        "response": out,
        "wall_seconds": time.perf_counter() - started,
        "load_seconds": out.get("load_duration", 0) / 1e9,
        "total_seconds": out.get("total_duration", 0) / 1e9,
    }
    eval_dur = out.get("eval_duration", 0) / 1e9
    eval_cnt = out.get("eval_count", 0)
    record["decode_tokens_per_second"] = (eval_cnt / eval_dur) if eval_dur else None
    record["text"] = out.get("message", {}).get("content", "")
    return record


def median(values: list[float | None]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return statistics.median(vals) if vals else None


def main() -> None:
    questions = [
        "Как запустить тесты? Укажи файл-источник.",
        "Что будет при пустом имени подписчика? Подтверди кодом.",
        "Где реализован unsubscribe? Проверь предпосылку вопроса.",
        "Какая CI-система запускает тесты? Если сведений нет, скажи об этом.",
        "Сохраняются ли подписки после перезапуска процесса? Подтверди кодом.",
    ]
    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    ab_dir = results_dir / "ab"
    ab_dir.mkdir(exist_ok=True)

    summary = {"model": MODEL, "temperature": TEMPERATURE, "num_ctx": NUM_CTX, "questions": []}

    for idx, q in enumerate(questions, start=1):
        # A: baseline (no system)
        # warm-up
        _ = run_once(q, system=False, seed=SEEDS[0])
        a_runs = [run_once(q, system=False, seed=s) for s in SEEDS]
        (ab_dir / f"q{idx}_A.json").write_text(json.dumps(a_runs, ensure_ascii=False, indent=2), encoding="utf-8")

        # B: system
        _ = run_once(q, system=True, seed=SEEDS[0])
        b_runs = [run_once(q, system=True, seed=s) for s in SEEDS]
        (ab_dir / f"q{idx}_B.json").write_text(json.dumps(b_runs, ensure_ascii=False, indent=2), encoding="utf-8")

        def m(field: str, runs: list[dict]) -> float | None:
            return median([r.get(field) for r in runs])

        summary["questions"].append({
            "q": q,
            "A": {
                "median_decode_tps": m("decode_tokens_per_second", a_runs),
                "median_total_seconds": m("total_seconds", a_runs),
                "answer": a_runs[-1]["text"],
            },
            "B": {
                "median_decode_tps": m("decode_tokens_per_second", b_runs),
                "median_total_seconds": m("total_seconds", b_runs),
                "answer": b_runs[-1]["text"],
            },
        })

    (results_dir / "ab_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", str(results_dir / "ab_summary.json"))


if __name__ == "__main__":
    main()
