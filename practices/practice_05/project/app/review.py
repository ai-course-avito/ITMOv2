"""Review pipeline; validates the final, redacted candidate atomically."""
import asyncio
import json

from app.config import Settings
from app.diff import parse_diff
from app.errors import ReviewError
from app.llm import DemoAdapter, LiveAdapter
from app.secrets import redact_text, redact_values


def validate_input(diff):
    if not isinstance(diff, str):
        raise ReviewError('INVALID_REQUEST')
    if len(diff) > 20000:
        raise ReviewError('DIFF_TOO_LARGE')
    if not diff.strip():
        raise ReviewError('INVALID_REQUEST')
    try:
        diff.encode('utf-8')
    except UnicodeEncodeError:
        raise ReviewError('INVALID_REQUEST') from None
    return parse_diff(diff)


def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ReviewError('INVALID_MODEL_OUTPUT')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        raise ReviewError('INVALID_MODEL_OUTPUT') from None
    return value.strip()


def validate_review(answer, rows):
    if not isinstance(answer, dict) or set(answer) != {'summary', 'risks', 'checks'}:
        raise ReviewError('INVALID_MODEL_OUTPUT')
    summary = _text(answer['summary'], 1500)
    risks, checks = answer['risks'], answer['checks']
    if not isinstance(risks, list) or len(risks) > 3:
        raise ReviewError('INVALID_MODEL_OUTPUT')
    if not isinstance(checks, list) or not 1 <= len(checks) <= 10:
        raise ReviewError('INVALID_MODEL_OUTPUT')
    known_lines = {(row.file, row.line, row.evidence) for row in rows}
    validated_risks = []
    for risk in risks:
        if not isinstance(risk, dict) or set(risk) != {'file', 'line', 'evidence', 'risk'}:
            raise ReviewError('INVALID_MODEL_OUTPUT')
        file, line, evidence = risk['file'], risk['line'], risk['evidence']
        if (not isinstance(file, str) or not file.strip() or type(line) is not int or line < 1
                or not isinstance(evidence, str) or not evidence or len(evidence) > 20000
                or (file, line, evidence) not in known_lines):
            raise ReviewError('INVALID_MODEL_OUTPUT')
        validated_risks.append({'file': file, 'line': line, 'evidence': evidence, 'risk': _text(risk['risk'], 1000)})
    return {'summary': summary, 'risks': validated_risks, 'checks': [_text(item, 500) for item in checks]}


class ReviewService:
    def __init__(self, settings=None, adapter=None, *, timeout_seconds=10):
        self.settings = settings or Settings()
        self.adapter = adapter or (LiveAdapter(self.settings) if self.settings.mode == 'live' else DemoAdapter())
        self.timeout_seconds = timeout_seconds

    async def review(self, diff):
        validate_input(diff)
        self.settings.validate()
        cleaned = redact_text(diff.replace('\r\n', '\n'))
        rows = parse_diff(cleaned)
        try:
            async with asyncio.timeout(self.timeout_seconds):
                candidate = await self.adapter.generate(cleaned)
        except TimeoutError:
            raise ReviewError('MODEL_TIMEOUT') from None
        try:
            if isinstance(candidate, str):
                candidate = json.loads(candidate)
            sanitized = redact_values(candidate)
            answer = validate_review(sanitized, rows)
        except (ValueError, RecursionError):
            raise ReviewError('INVALID_MODEL_OUTPUT') from None
        return {'mode': self.settings.mode, **answer}
