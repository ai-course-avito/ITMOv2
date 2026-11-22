"""Проверка unified diff по правилам API-1 и SEC-1. Только стандартная библиотека."""
import re

API1_LIMIT = 20_000

SECRET_PATTERNS = [
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("assignment", re.compile(r"(?i)\b(password|passwd|secret|token|api_key|apikey)\s*[:=]\s*['\"]?[^\s'\"]{4,}")),
]

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class DiffError(ValueError):
    """Вход не является unified diff."""


def _redact(text: str) -> str:
    for _, pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text.strip()[:120]


def scan_diff_text(text: str) -> dict:
    if "diff --git" not in text and not re.search(r"^@@ ", text, re.M):
        raise DiffError("input is not a unified diff: no 'diff --git' header or '@@' hunk")

    files: list[str] = []
    secrets: list[dict] = []
    added = 0
    current_file = None
    new_line = 0

    for raw in text.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            current_file = path[2:] if path.startswith("b/") else path
            if current_file not in files:
                files.append(current_file)
            continue
        if raw.startswith("--- "):
            continue
        hunk = HUNK.match(raw)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if raw.startswith("+"):
            added += 1
            for kind, pattern in SECRET_PATTERNS:
                if pattern.search(raw):
                    secrets.append({"file": current_file, "line": new_line, "kind": kind,
                                    "snippet": _redact(raw[1:])})
                    break
            new_line += 1
        elif raw.startswith(" "):
            new_line += 1

    chars = len(text)
    reasons = []
    if chars > API1_LIMIT:
        reasons.append(f"API-1: diff has {chars} chars, limit is {API1_LIMIT}")
    if secrets:
        reasons.append(f"SEC-1: {len(secrets)} secret(s) in added lines")
    return {
        "chars": chars,
        "limit": API1_LIMIT,
        "within_api1_limit": chars <= API1_LIMIT,
        "files": files,
        "added_lines": added,
        "secrets": secrets,
        "verdict": "blocked" if reasons else "ok",
        "reasons": reasons,
    }
