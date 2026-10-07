"""Ask itmo-agent questions about demo/ via Ollama API, bypassing OpenCode."""
import json, time, urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
files = ["README.md", "service.py", "test_service.py", "Makefile"]
context = "\n\n".join(
    f"=== {f} ===\n" + "".join(f"{i}: {l}\n" for i, l in enumerate((root / "demo" / f).read_text().splitlines(), 1))
    for f in files)
system = (root / "demo/repo-system.txt").read_text()
questions = {
    "q1": "Как запустить тесты? Укажи файл-источник.",
    "q2": "Что будет при пустом имени подписчика? Подтверди кодом.",
    "q3": "Где реализован unsubscribe? Проверь предпосылку вопроса.",
    "q4": "Какая CI-система запускает тесты? Если сведений нет, скажи об этом. Сохраняются ли подписки после перезапуска процесса? Подтверди кодом.",
}
for key, q in questions.items():
    if (root / f"results/agent_{key}.json").exists():
        continue
    payload = {"model": "itmo-agent", "stream": False, "think": False,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": "Файлы проекта:\n\n" + context + "\n\nВопрос: " + q}],
               "options": {"temperature": 0.2, "seed": 42, "num_ctx": 65536, "num_predict": 512}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        ans = json.load(r)
    d = ans.get("eval_duration", 0)
    rec = {"question": q, "request": payload, "response": ans, "wall_seconds": time.perf_counter() - t,
           "load_seconds": ans.get("load_duration", 0) / 1e9,
           "decode_tokens_per_second": ans["eval_count"] / (d / 1e9) if d else None}
    with (root / f"results/agent_{key}.json").open("x", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print("=====", key, q, "| %.1fs load %.1fs %.2f t/s in/out %s/%s" % (
        rec["wall_seconds"], rec["load_seconds"], rec["decode_tokens_per_second"],
        ans["prompt_eval_count"], ans["eval_count"]))
    print(ans["message"]["content"], flush=True)
