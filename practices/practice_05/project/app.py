import json
import os
import threading
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

    with _lock:
        tasks = _load_tasks()
        next_id = (max((t.get('id', 0) for t in tasks), default=0) + 1)
        task = {'id': next_id, 'title': title, 'done': False}
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
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='127.0.0.1', port=port, debug=True)
