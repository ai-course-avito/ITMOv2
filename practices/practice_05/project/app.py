import json
import os
import re
import threading
from datetime import date
from flask import Flask, request, jsonify, send_from_directory


# Simple Flask app serving a minimal task manager with file-based storage.
app = Flask(__name__, static_folder='static', static_url_path='/static')

DATA_FILE = os.path.join(os.path.dirname(__file__), 'tasks.json')
_lock = threading.Lock()


def _ensure_data_file():
    """Create the data file if it doesn't exist."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)


def _load_tasks():
    _ensure_data_file()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Reset on corrupt file to keep the app usable.
            return []


def _save_tasks(tasks):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# --- Time validation helpers (ISO 8601) ---
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DT_MINUTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")


def _is_iso_date(d: str) -> bool:
    if not isinstance(d, str):
        return False
    if not _DATE_RE.match(d):
        return False
    try:
        # fromisoformat enforces YYYY-MM-DD semantics
        date.fromisoformat(d)
        return True
    except ValueError:
        return False


def _is_iso_datetime_minute(s: str) -> bool:
    if not isinstance(s, str):
        return False
    # Enforce presence of timezone and no seconds
    return _DT_MINUTE_RE.match(s) is not None


def _validate_time_fields(payload):
    """
    Validate mutually exclusive time modes with optional absence of time.
    Rules:
    - If both all_day and (start/end) present -> time_mode_conflict
    - If start or end present, both must be present and match ISO 8601 to-minute with offset; seconds not allowed -> invalid_time_precision
    - If all_day present, must be YYYY-MM-DD -> invalid_time_format
    - Absence of all time fields is allowed
    Returns (ok: bool, err_code: str|None)
    """
    all_day = payload.get('all_day')
    when = payload.get('when')
    start = payload.get('start')
    end = payload.get('end')

    has_all_day = all_day is not None and all_day != ''
    has_when = when is not None and when != ''
    has_start = start is not None and start != ''
    has_end = end is not None and end != ''

    # Only one of: all_day, when, (start+end)
    if sum([1 if has_all_day else 0, 1 if has_when else 0, 1 if (has_start or has_end) else 0]) > 1:
        return False, 'time_mode_conflict'

    if has_when:
        if not _is_iso_datetime_minute(when):
            return False, 'invalid_time_precision'

    if has_start or has_end:
        if not (has_start and has_end):
            return False, 'invalid_time_fields'
        if not _is_iso_datetime_minute(start) or not _is_iso_datetime_minute(end):
            return False, 'invalid_time_precision'

    if has_all_day and not _is_iso_date(all_day):
        return False, 'invalid_time_format'

    return True, None


@app.get('/')
def index():
    # Serve the static index page.
    return send_from_directory(app.static_folder, 'index.html')


@app.get('/api/tasks')
def list_tasks():
    with _lock:
        tasks = _load_tasks()
    return jsonify(tasks)


@app.post('/api/tasks')
def create_task():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400

    ok, err = _validate_time_fields(data)
    if not ok:
        return jsonify({'error': err}), 400

    with _lock:
        tasks = _load_tasks()
        next_id = (max((t.get('id', 0) for t in tasks), default=0) + 1)
        task = {'id': next_id, 'title': title, 'done': False}
        # Add optional time fields if provided
        if (data.get('all_day') or ''):
            task['all_day'] = data['all_day']
        if (data.get('when') or ''):
            task['when'] = data['when']
        if (data.get('start') or '') and (data.get('end') or ''):
            task['start'] = data['start']
            task['end'] = data['end']
        tasks.append(task)
        _save_tasks(tasks)

    return jsonify(task), 201


@app.patch('/api/tasks/<int:task_id>')
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    with _lock:
        tasks = _load_tasks()
        for t in tasks:
            if t.get('id') == task_id:
                if 'done' in data:
                    t['done'] = bool(data['done'])
                if 'title' in data:
                    title = (data.get('title') or '').strip()
                    if title:
                        t['title'] = title
                # Handle time fields if present in patch
                if any(k in data for k in ('all_day', 'when', 'start', 'end')):
                    # Build candidate values combining existing and patch
                    cand = {
                        'all_day': data.get('all_day', t.get('all_day')),
                        'when': data.get('when', t.get('when')),
                        'start': data.get('start', t.get('start')),
                        'end': data.get('end', t.get('end')),
                    }
                    # Interpret explicit null/empty as clearing
                    if cand['all_day'] in (None, ''):
                        cand['all_day'] = None
                    if cand['when'] in (None, ''):
                        cand['when'] = None
                    if cand['start'] in (None, ''):
                        cand['start'] = None
                    if cand['end'] in (None, ''):
                        cand['end'] = None

                    ok, err = _validate_time_fields(cand)
                    if not ok:
                        return jsonify({'error': err}), 400

                    # Apply: either all_day or when or start/end or none
                    for key in ('all_day', 'when', 'start', 'end'):
                        if cand.get(key) is None:
                            t.pop(key, None)
                        else:
                            t[key] = cand[key]
                _save_tasks(tasks)
                return jsonify(t)

    return jsonify({'error': 'not found'}), 404


@app.delete('/api/tasks/<int:task_id>')
def delete_task(task_id: int):
    with _lock:
        tasks = _load_tasks()
        new_tasks = [t for t in tasks if t.get('id') != task_id]
        if len(new_tasks) == len(tasks):
            return jsonify({'error': 'not found'}), 404
        _save_tasks(new_tasks)

    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    app.run(host='127.0.0.1', port=port, debug=True)
