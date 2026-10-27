"""Finite, documented redaction rules; not a detector for every possible secret."""
import re

MARKER = '[REDACTED]'
ASSIGNMENT = re.compile(
    r'''(?i)(?<![\w])(?P<key>["']?(?:token|password|passwd|secret|api_key)["']?)'''
    r'''(?P<sep>[ \t]*[:=][ \t]*)(?P<value>"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|[^\s,;]+)'''
)
BEARER = re.compile(r'''(?i)(\bBearer[ \t]+)([^\s'"\r\n]+)''')
TOKEN = re.compile(r'(?<![A-Za-z0-9_-])(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])')
PEM_BLOCK = re.compile(
    r'(?P<begin>-----BEGIN (?P<kind>(?:RSA |EC |OPENSSH )?PRIVATE KEY)-----)'
    r'(?P<payload>.*?)(?P<end>-----END (?P=kind)-----|\Z)', re.DOTALL
)
STRUCTURAL = ('diff --git ', '--- ', '+++ ', '@@ ', 'index ', 'new file mode ', 'deleted file mode ',
              'old mode ', 'new mode ', 'similarity index ', 'dissimilarity index ', 'rename from ', 'rename to ')


def _replace_assignment(match):
    value = match['value']
    if value.startswith(('"', "'")) and value.endswith(value[0]):
        value = value[0] + (MARKER if len(value) > 2 else '') + value[-1]
    else:
        value = MARKER
    return match['key'] + match['sep'] + value


def _replace_pem(match):
    output = []
    for index, raw in enumerate(match['payload'].split('\n')):
        ending = '\r' if raw.endswith('\r') else ''
        line = raw[:-1] if ending else raw
        # The first fragment follows BEGIN on the same line, so a leading +
        # there is key payload, not a diff sign. Preserve signs on later lines.
        if line and not (index > 0 and line.startswith(STRUCTURAL)):
            prefix = line[0] if index > 0 and line[0] in ('+', '-', ' ') else ''
            payload = line[len(prefix):]
            line = prefix + (MARKER if payload else '')
        output.append(line + ending)
    return match['begin'] + '\n'.join(output) + match['end']


def redact_text(text):
    # Also covers BEGIN/payload/END on one line and an absent closing marker.
    result = PEM_BLOCK.sub(_replace_pem, text)
    result = ASSIGNMENT.sub(_replace_assignment, result)
    result = BEARER.sub(lambda match: match[1] + MARKER, result)
    return TOKEN.sub(MARKER, result)


def redact_values(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_values(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_values(item) for key, item in value.items()}
    return value
