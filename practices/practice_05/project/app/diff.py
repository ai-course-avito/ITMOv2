"""Parse the agreed textual subset without applying a patch or reading files."""
from dataclasses import dataclass
import re

from app.errors import ReviewError

HUNK = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(?:.*)$')
META = ('index ', 'new file mode ', 'deleted file mode ', 'old mode ', 'new mode ',
        'similarity index ', 'dissimilarity index ', 'rename from ', 'rename to ')
UNSUPPORTED = ('diff --cc ', 'diff --combined ', '@@@', 'GIT binary patch', 'Binary files ')


@dataclass(frozen=True)
class DiffLine:
    file: str
    line: int
    evidence: str
    side: str


def _path(header):
    value = header[4:].split('\t', 1)[0]
    if not value.strip():
        raise ReviewError('INVALID_DIFF')
    if value.startswith('"') or '\\' in value:
        raise ReviewError('UNSUPPORTED_DIFF')
    return value[2:] if value.startswith(('a/', 'b/')) else value


def parse_diff(diff):
    lines = diff.replace('\r\n', '\n').split('\n')
    if any(line.startswith(UNSUPPORTED) for line in lines):
        raise ReviewError('UNSUPPORTED_DIFF')
    if any(line.startswith(('rename from ', 'rename to ')) for line in lines) and not any(HUNK.match(line) for line in lines):
        raise ReviewError('UNSUPPORTED_DIFF')
    rows = []
    file = None
    in_hunk = False
    file_has_hunk = False
    pending_git_header = False
    changed = False
    old = new = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('diff --git '):
            if pending_git_header or (file is not None and not file_has_hunk):
                raise ReviewError('INVALID_DIFF')
            file = None
            in_hunk = file_has_hunk = False
            pending_git_header = True
            i += 1
            continue
        # Inside a hunk, ---/+++ may be ordinary removed/added text. A new
        # unmarked file needs its own immediately following hunk header.
        header_pair = line.startswith('--- ') and i + 1 < len(lines) and lines[i+1].startswith('+++ ')
        starts_file = not in_hunk or (i + 2 < len(lines) and HUNK.match(lines[i+2]))
        if header_pair and starts_file:
            if file is not None and not file_has_hunk:
                raise ReviewError('INVALID_DIFF')
            previous, following = _path(line), _path(lines[i+1])
            file = previous if following == '/dev/null' else following
            if file == '/dev/null':
                raise ReviewError('INVALID_DIFF')
            in_hunk = file_has_hunk = False
            pending_git_header = False
            i += 2
            continue
        match = HUNK.match(line)
        if match:
            if file is None:
                raise ReviewError('INVALID_DIFF')
            old, new = map(int, match.groups())
            in_hunk = file_has_hunk = True
            i += 1
            continue
        if in_hunk:
            if line == '\\ No newline at end of file':
                i += 1
                continue
            if not line and i == len(lines)-1:
                break
            if not line or line[0] not in ('+', '-', ' '):
                raise ReviewError('INVALID_DIFF')
            prefix = line[0]
            coordinate, side = (old, 'old') if prefix == '-' else (new, 'new')
            if coordinate < 1:
                raise ReviewError('INVALID_DIFF')
            rows.append(DiffLine(file, coordinate, line, side))
            if prefix != '+':
                old += 1
            if prefix != '-':
                new += 1
            changed |= prefix in ('+', '-')
        elif line and not line.startswith(META):
            raise ReviewError('INVALID_DIFF')
        i += 1
    if pending_git_header or not rows or not changed or not file_has_hunk:
        raise ReviewError('INVALID_DIFF')
    return rows
