#!/usr/bin/env python3
"""
Export summary report (/export-report) per spec and logic-spec.

- Parses metrics from practices/practice_03/lab/results/*.json
  Extracts: wall_seconds, decode_tokens_per_second (top-level floats)
- Optionally includes artifacts: practices/practice_01/prompts.md, practices/practice_03/REPORT.md
- Generates Markdown or HTML report under reports/report-YYYY-MM-DD.{md|html}
- Prints summary with path, counts, and status. Prints "Нет данных для отчёта" if no data.

Constraints: read-only for sources; only writes to reports/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple


RESULTS_GLOB = os.path.join("practices", "practice_03", "lab", "results", "*.json")
ARTIFACT_PROMPTS = os.path.join("practices", "practice_01", "prompts.md")
ARTIFACT_REPORT = os.path.join("practices", "practice_03", "REPORT.md")
REPORTS_DIR = "reports"


@dataclass
class MetricRow:
    filename: str
    wall_seconds: float
    decode_tokens_per_second: float


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export summary report from practice results")
    parser.add_argument(
        "--format",
        choices=["md", "html"],
        default="md",
        help="Report format: md or html (default: md)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--include-artifacts",
        action="store_true",
        help="Include artifacts (prompts.md, REPORT.md)",
    )
    group.add_argument(
        "--metrics-only",
        action="store_true",
        help="Include only metrics (no artifacts)",
    )
    return parser.parse_args(argv)


def load_json_metrics(path: str) -> Tuple[Optional[MetricRow], Optional[str]]:
    """Returns (MetricRow, error) where only one is non-None.

    Error is a short string explanation; do not raise to keep processing.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        return None, f"JSON parse error: {e}"

    # Validate required fields at top level
    try:
        ws = float(data["wall_seconds"])  # may raise KeyError/TypeError/ValueError
        dps = float(data["decode_tokens_per_second"])  # same as above
    except Exception as e:  # noqa: BLE001
        return None, f"Missing/invalid metrics: {e}"

    filename = os.path.basename(path)
    return MetricRow(filename=filename, wall_seconds=ws, decode_tokens_per_second=dps), None


def read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().rstrip()
    except FileNotFoundError:
        return "файл не найден"
    except Exception as e:  # noqa: BLE001
        return f"ошибка чтения: {e}"


def format_markdown(
    date_str: str,
    rows: List[MetricRow],
    include_artifacts: bool,
    prompts_text: Optional[str],
    report_text: Optional[str],
    processed_count: int,
    metrics_count: int,
    parse_errors: int,
) -> str:
    header = f"# Отчёт по результатам практик — {date_str}\n\n"
    # Table header
    md = [header, "## Метрики\n", "\n", "| Файл | Время, с | Скорость, tok/s |\n", "|---|---|---|\n"]
    for r in rows:
        md.append(f"| {r.filename} | {r.wall_seconds:.2f} | {r.decode_tokens_per_second:.2f} |\n")
    if rows:
        avg_w = sum(r.wall_seconds for r in rows) / len(rows)
        avg_d = sum(r.decode_tokens_per_second for r in rows) / len(rows)
        md.append(f"| **Среднее** | **{avg_w:.2f}** | **{avg_d:.2f}** |\n")

    if include_artifacts:
        md.append("\n## Артефакты\n\n")
        md.append("### practices/practice_01/prompts.md\n\n")
        md.append((prompts_text or "").strip() + "\n\n")
        md.append("### practices/practice_03/REPORT.md\n\n")
        md.append((report_text or "").strip() + "\n\n")

    md.append("---\n")
    md.append(f"Сгенерировано: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    md.append(f"Файлов обработано: {processed_count}\n")
    md.append(f"Метрик извлечено: {metrics_count}\n")
    if parse_errors:
        md.append(f"Ошибок парсинга: {parse_errors}\n")
    md.append("Статус: Success\n")
    return "".join(md)


def format_html(
    date_str: str,
    rows: List[MetricRow],
    include_artifacts: bool,
    prompts_text: Optional[str],
    report_text: Optional[str],
    processed_count: int,
    metrics_count: int,
    parse_errors: int,
) -> str:
    avg_w = sum(r.wall_seconds for r in rows) / len(rows) if rows else 0.0
    avg_d = sum(r.decode_tokens_per_second for r in rows) / len(rows) if rows else 0.0
    css = (
        "table{border-collapse:collapse}"
        "th,td{border:1px solid #ccc;padding:4px 8px}"
        "code,pre{background:#f7f7f7;padding:8px;display:block;white-space:pre-wrap}"
        "h1,h2,h3{font-family:sans-serif}"
    )
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>Отчёт — {date_str}</title>",
        f"<style>{css}</style>",
        "</head><body>",
        f"<h1>Отчёт по результатам практик — {date_str}</h1>",
        "<h2>Метрики</h2>",
        "<table><thead><tr><th>Файл</th><th>Время, с</th><th>Скорость, tok/s</th></tr></thead><tbody>",
    ]
    for r in rows:
        parts.append(
            f"<tr><td>{r.filename}</td><td>{r.wall_seconds:.2f}</td><td>{r.decode_tokens_per_second:.2f}</td></tr>"
        )
    if rows:
        parts.append(
            f"<tr><td><strong>Среднее</strong></td><td><strong>{avg_w:.2f}</strong></td><td><strong>{avg_d:.2f}</strong></td></tr>"
        )
    parts.append("</tbody></table>")

    if include_artifacts:
        parts.append("<h2>Артефакты</h2>")
        parts.append("<h3>practices/practice_01/prompts.md</h3>")
        parts.append(f"<pre><code>{html_escape(prompts_text or '')}</code></pre>")
        parts.append("<h3>practices/practice_03/REPORT.md</h3>")
        parts.append(f"<pre><code>{html_escape(report_text or '')}</code></pre>")

    parts.append("<hr/>")
    parts.append(f"<p>Сгенерировано: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>")
    parts.append(f"<p>Файлов обработано: {processed_count}</p>")
    parts.append(f"<p>Метрик извлечено: {metrics_count}</p>")
    if parse_errors:
        parts.append(f"<p>Ошибок парсинга: {parse_errors}</p>")
    parts.append("<p>Статус: Success</p>")
    parts.append("</body></html>")
    return "".join(parts)


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&#39;")
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    include_artifacts = True if args.include_artifacts else False
    if args.metrics_only:
        include_artifacts = False

    # Collect result JSON files
    json_files = sorted(glob.glob(RESULTS_GLOB))

    if not json_files:
        print("Нет данных для отчёта")
        return 0

    rows: List[MetricRow] = []
    processed = 0
    parse_errors = 0
    for path in json_files:
        processed += 1
        row, err = load_json_metrics(path)
        if row is not None:
            rows.append(row)
        else:
            parse_errors += 1

    if not rows:
        print("Нет данных для отчёта")
        return 0

    # Sort rows by filename
    rows.sort(key=lambda r: r.filename.lower())

    metrics_count = len(rows) * 2  # two metrics per file

    prompts_text = report_text = None
    if include_artifacts:
        prompts_text = read_text_file(ARTIFACT_PROMPTS)
        report_text = read_text_file(ARTIFACT_REPORT)

    date_str = dt.date.today().strftime("%Y-%m-%d")
    ext = "md" if args.format == "md" else "html"
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, f"report-{date_str}.{ext}")

    if args.format == "md":
        content = format_markdown(
            date_str,
            rows,
            include_artifacts,
            prompts_text,
            report_text,
            processed,
            metrics_count,
            parse_errors,
        )
    else:
        content = format_html(
            date_str,
            rows,
            include_artifacts,
            prompts_text,
            report_text,
            processed,
            metrics_count,
            parse_errors,
        )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Summary output per spec
    print(f"Путь: {out_path}")
    print(f"Краткое резюме: файлов {processed}, метрик {metrics_count}, статус Success")
    if parse_errors:
        print(f"Примечание: ошибок парсинга {parse_errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
