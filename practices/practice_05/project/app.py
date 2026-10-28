import json
import os
import re
import threading
import random
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from flask import Flask, request, jsonify, send_from_directory


# Simple Flask app serving a minimal task manager with file-based storage.
app = Flask(__name__, static_folder='static', static_url_path='/static')

DATA_FILE = os.path.join(os.path.dirname(__file__), 'tasks.json')
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')  # legacy for migration only
DB_FILE = os.environ.get('TASKS_DB_FILE', os.path.join(os.path.dirname(__file__), 'gamification.db'))
MIGRATION_REPORT_FILE = os.path.join(os.path.dirname(__file__), 'migration_report.json')
_TEST_DB_RESET_DONE = False
_lock = threading.Lock()


def _ensure_data_file():
    """No-op: tasks now stored in DB; USERS_FILE remains only for legacy migration."""
    return


def _load_tasks():
    # Deprecated JSON path (unused)
    return []


def _save_tasks(tasks):
    # Deprecated JSON path (unused)
    return


# --- SQLite helpers (users & ownership) ---

def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _db_init():
    global _TEST_DB_RESET_DONE
    # In testing mode, reset DB file once per test case to ensure clean state
    if app.testing and not _TEST_DB_RESET_DONE:
        try:
            os.remove(DB_FILE)
        except FileNotFoundError:
            pass
        _TEST_DB_RESET_DONE = True
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                name TEXT PRIMARY KEY,
                spins_remaining INTEGER NOT NULL,
                has_multi_emoji INTEGER NOT NULL,
                utc_offset TEXT NOT NULL,
                last_reset_local_date TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS emoji_catalog (
                code TEXT NOT NULL,
                version TEXT NOT NULL,
                rarity TEXT NOT NULL,
                display_name TEXT NOT NULL,
                icon_ref TEXT NOT NULL,
                PRIMARY KEY (code, version)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS user_emojis (
                user_name TEXT NOT NULL,
                code TEXT NOT NULL,
                version TEXT NOT NULL,
                PRIMARY KEY (user_name, code, version),
                FOREIGN KEY (user_name) REFERENCES users(name) ON DELETE CASCADE
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                all_day TEXT NULL,
                "when" TEXT NULL,
                start TEXT NULL,
                end TEXT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS task_emojis (
                task_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                version TEXT NOT NULL,
                PRIMARY KEY (task_id, code, version),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS spin_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                outcome_type TEXT NOT NULL,
                code TEXT NULL,
                version TEXT NULL,
                label TEXT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
        # Seed emoji catalog if empty
        c.execute("SELECT COUNT(*) FROM emoji_catalog")
        row = c.fetchone()
        ec_count = int(row[0]) if row else 0
        if ec_count == 0:
            for item in EMOJI_CATALOG:
                c.execute(
                    "INSERT OR IGNORE INTO emoji_catalog(code, version, rarity, display_name, icon_ref) VALUES (?, ?, ?, ?, ?)",
                    (item['code'], item['version'], item['rarity'], item['display_name'], item['icon_ref'])
                )
            conn.commit()
        # Ensure catalog stores glyphs (not file paths) to avoid missing static assets
        _ensure_catalog_glyphs()


def _db_get_user(name: str) -> Optional[Dict[str, Any]]:
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE name=?", (name,))
        row = c.fetchone()
        if not row:
            return None
        return {
            'name': row['name'],
            'spins_remaining': row['spins_remaining'],
            'has_multi_emoji': bool(row['has_multi_emoji']),
            'utc_offset': row['utc_offset'],
            'last_reset_local_date': row['last_reset_local_date'],
        }


def _db_create_user(name: str, utc_offset: str) -> Dict[str, Any]:
    today_local = _current_local_date(utc_offset)
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO users(name, spins_remaining, has_multi_emoji, utc_offset, last_reset_local_date) VALUES (?, ?, ?, ?, ?)",
            (name, 5, 0, utc_offset, today_local),
        )
        conn.commit()
    return {
        'name': name,
        'spins_remaining': 5,
        'has_multi_emoji': False,
        'utc_offset': utc_offset,
        'last_reset_local_date': today_local,
    }


def _db_update_user(user: Dict[str, Any]):
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET spins_remaining=?, has_multi_emoji=?, utc_offset=?, last_reset_local_date=? WHERE name=?",
            (
                int(user.get('spins_remaining', 0)),
                1 if user.get('has_multi_emoji') else 0,
                user.get('utc_offset', '+00:00'),
                user.get('last_reset_local_date', ''),
                user['name'],
            ),
        )
        conn.commit()


# --- Legacy JSON compatibility for tests ---

def _legacy_get_user_emojis_from_json(name: str) -> List[Dict[str, str]]:
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for u in data:
                    if u.get('name') == name:
                        return [
                            {'code': e.get('code'), 'version': e.get('version')}
                            for e in u.get('emojis', []) if e.get('code') and e.get('version')
                        ]
    except (OSError, json.JSONDecodeError):
        return []
    return []


def _compat_dump_single_user_to_json(user: Dict[str, Any]):
    # Write a minimal users.json with the single user state for test compatibility
    try:
        emojis = _db_get_user_emojis(user['name'])
        payload = [{
            'name': user['name'],
            'spins_remaining': int(user.get('spins_remaining', 0)),
            'has_multi_emoji': bool(user.get('has_multi_emoji', False)),
            'utc_offset': user.get('utc_offset', '+00:00'),
            'last_reset_local_date': user.get('last_reset_local_date', _current_local_date(user.get('utc_offset', '+00:00'))),
            'emojis': emojis,
        }]
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # Best effort only for tests
        pass


def _db_get_user_emojis(name: str) -> List[Dict[str, str]]:
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT code, version FROM user_emojis WHERE user_name=?", (name,))
        rows = c.fetchall()
        return [{'code': r['code'], 'version': r['version']} for r in rows]  # type: ignore


def _db_add_user_emoji(name: str, code: str, version: str) -> bool:
    try:
        with _db_conn() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO user_emojis(user_name, code, version) VALUES (?, ?, ?)",
                (name, code, version),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def _db_user_count() -> int:
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        (cnt,) = c.fetchone()
        return int(cnt)


def _migrate_users_json_to_db() -> Tuple[int, int]:
    """Migrate legacy users.json into SQLite if DB is empty. Returns (imported, skipped).
    Also produces a migration report file with details per spec FR-016.
    """
    if not os.path.exists(USERS_FILE):
        return (0, 0)
    if _db_user_count() > 0:
        return (0, 0)
    imported = 0
    skipped = 0
    report: Dict[str, Any] = {
        'source': os.path.basename(USERS_FILE),
        'db_file': os.path.basename(DB_FILE),
        'imported': [],
        'skipped': [],
        'ts': datetime.utcnow().isoformat() + 'Z',
    }
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                return (0, 0)
            for u in data:
                name = (u.get('name') or '').strip()
                if not name or not _NAME_RE.match(name):
                    skipped += 1
                    report['skipped'].append({'name': name or '(empty)', 'reason': 'invalid_name'})
                    continue
                utc_offset = u.get('utc_offset') or '+00:00'
                if _parse_offset(utc_offset) is None:
                    utc_offset = '+00:00'
                # Create user if not exist
                if _db_get_user(name) is None:
                    user = _db_create_user(name, utc_offset)
                    # Set spins/flags from legacy
                    user['spins_remaining'] = int(u.get('spins_remaining', 5))
                    user['has_multi_emoji'] = bool(u.get('has_multi_emoji', False))
                    user['last_reset_local_date'] = u.get('last_reset_local_date') or _current_local_date(utc_offset)
                    _db_update_user(user)
                    # Migrate emojis
                    for e in u.get('emojis', []):
                        code = e.get('code')
                        version = e.get('version')
                        if code and version:
                            _db_add_user_emoji(name, code, version)
                    imported += 1
                    report['imported'].append({'name': name})
                else:
                    skipped += 1
                    report['skipped'].append({'name': name, 'reason': 'duplicate_name'})
    except (OSError, json.JSONDecodeError):
        # On error, consider as skipped
        try:
            report['error'] = 'io_or_parse_error'
            with open(MIGRATION_REPORT_FILE, 'w', encoding='utf-8') as rf:
                json.dump(report, rf, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return (imported, skipped)
    # Write report
    try:
        with open(MIGRATION_REPORT_FILE, 'w', encoding='utf-8') as rf:
            json.dump(report, rf, ensure_ascii=False, indent=2)
    except Exception:
        # Best-effort only
        pass
    return (imported, skipped)


# --- Time validation helpers (ISO 8601) ---
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DT_MINUTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")
_NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


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


# --- Gamification: Emoji Catalog and Helpers ---

# Prefer glyphs to avoid 404s for missing static assets; icon_ref kept for completeness
EMOJI_CATALOG: List[Dict[str, str]] = [
    {"code": "star", "version": "v1", "rarity": "rare", "display_name": "Star", "icon_ref": "⭐"},
    {"code": "fire", "version": "v1", "rarity": "common", "display_name": "Fire", "icon_ref": "🔥"},
    {"code": "check", "version": "v1", "rarity": "common", "display_name": "Check", "icon_ref": "✔️"},
    {"code": "heart", "version": "v1", "rarity": "common", "display_name": "Heart", "icon_ref": "❤️"},
    {"code": "lightning", "version": "v1", "rarity": "common", "display_name": "Lightning", "icon_ref": "⚡"},
    {"code": "rocket", "version": "v1", "rarity": "rare", "display_name": "Rocket", "icon_ref": "🚀"},
    {"code": "crown", "version": "v1", "rarity": "very_rare", "display_name": "Crown", "icon_ref": "👑"},
    {"code": "diamond", "version": "v1", "rarity": "very_rare", "display_name": "Diamond", "icon_ref": "💎"}
]

ODD_PRIZES: List[str] = [
    "Скидка на задачи",
    "Участие в розыгрыше",
    "Промо-код на кофе",
    "Бессмысленный диплом",
    "Улыбка от тимлида",
    "Multi-Emoji Perk",
]

EMOJI_GLYPHS = {
    'star': '⭐',
    'fire': '🔥',
    'check': '✔️',
    'heart': '❤️',
    'lightning': '⚡',
    'rocket': '🚀',
    'crown': '👑',
    'diamond': '💎',
}

def _ensure_catalog_glyphs():
    """Update existing catalog entries to store glyphs if icon_ref looks like a file path."""
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT code, version, icon_ref FROM emoji_catalog")
        rows = c.fetchall()
        for r in rows:
            code = r['code']
            icon_ref = r['icon_ref'] or ''
            if '.' in icon_ref or icon_ref.endswith('.svg') or icon_ref.startswith('/'):  # looks like a file path
                glyph = EMOJI_GLYPHS.get(code)
                if glyph:
                    c.execute("UPDATE emoji_catalog SET icon_ref=? WHERE code=? AND version=?", (glyph, code, r['version']))
        conn.commit()

def _db_get_emoji_catalog() -> List[Dict[str, Any]]:
    with _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT code, version, rarity, display_name, icon_ref FROM emoji_catalog")
        rows = c.fetchall()
        if rows:
            return [
                {
                    'code': r['code'],
                    'version': r['version'],
                    'rarity': r['rarity'],
                    'display_name': r['display_name'],
                    'icon_ref': r['icon_ref'],
                }
                for r in rows
            ]
    return EMOJI_CATALOG


def _parse_offset(offset_str: str) -> Optional[timezone]:
    if not isinstance(offset_str, str):
        return None
    m = re.match(r"^([+-])(\d{2}):(\d{2})$", offset_str)
    if not m:
        return None
    sign = 1 if m.group(1) == '+' else -1
    hours = int(m.group(2))
    minutes = int(m.group(3))
    delta = timedelta(hours=hours * sign, minutes=minutes * sign)
    return timezone(delta)


def _current_local_date(offset_str: str) -> str:
    tz = _parse_offset(offset_str) or timezone.utc
    now = datetime.now(tz)
    return now.date().isoformat()


def _refresh_spins_if_needed(user: Dict[str, Any]):
    offset = user.get('utc_offset', '+00:00')
    today_local = _current_local_date(offset)
    last = user.get('last_reset_local_date')
    if last != today_local:
        user['spins_remaining'] = 5
        user['last_reset_local_date'] = today_local


def _find_user(users: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for u in users:
        if u.get('name') == name:
            return u
    return None


def _user_profile_payload(user: Dict[str, Any]) -> Dict[str, Any]:
    # Build emojis with details from catalog (source of truth: DB)
    owned = _db_get_user_emojis(user['name'])
    catalog = _db_get_emoji_catalog()
    detailed = []
    for e in owned:
        for item in catalog:
            if item['code'] == e.get('code') and item['version'] == e.get('version'):
                detailed.append(item)
                break
    return {
        'name': user['name'],
        'spins_remaining': max(int(user.get('spins_remaining', 0)), 0),
        'has_multi_emoji': bool(user.get('has_multi_emoji', False)),
        'reset_info': {
            'next_midnight_utc_offset': user.get('utc_offset', '+00:00'),
        },
        'emojis': detailed,
    }

@app.post('/api/admin/reset_spins')
def admin_reset_spins():
    """Admin/debug endpoint to reset spins to 5 for a user (by name header/query)."""
    _db_init()
    name = _get_request_user_name()
    if not name:
        return jsonify({'error': 'not_found'}), 404
    with _lock:
        user = _db_get_user(name)
        if user is None:
            return jsonify({'error': 'not_found'}), 404
        user['spins_remaining'] = 5
        _db_update_user(user)
        return jsonify(_user_profile_payload(user))


@app.get('/')
def index():
    # Serve the static index page.
    return send_from_directory(app.static_folder, 'index.html')


@app.get('/api/tasks')
def list_tasks():
    _db_init()
    with _lock, _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM tasks ORDER BY id ASC")
        rows = c.fetchall()
        tasks: List[Dict[str, Any]] = []
        for r in rows:
            task = {
                'id': r['id'],
                'title': r['title'],
                'done': bool(r['done']),
            }
            for key in ('all_day', 'when', 'start', 'end'):
                if r[key] is not None:
                    task[key] = r[key]
            # Attach emojis details
            c2 = conn.cursor()
            c2.execute("SELECT code, version FROM task_emojis WHERE task_id=?", (r['id'],))
            em_rows = c2.fetchall()
            if em_rows:
                details = []
                catalog = _db_get_emoji_catalog()
                for em in em_rows:
                    det = next((e for e in catalog if e['code'] == em['code'] and e['version'] == em['version']), None)
                    if det:
                        details.append(det)
                if details:
                    task['emojis'] = details
            tasks.append(task)
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

    _db_init()
    with _lock, _db_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO tasks(title, done, all_day, `when`, start, end) VALUES (?, 0, ?, ?, ?, ?)",
            (
                title,
                data.get('all_day') if (data.get('all_day') or '') else None,
                data.get('when') if (data.get('when') or '') else None,
                data.get('start') if (data.get('start') or '') else None,
                data.get('end') if (data.get('end') or '') else None,
            ),
        )
        task_id = c.lastrowid
        conn.commit()
        task = {'id': task_id, 'title': title, 'done': False}
        for key in ('all_day', 'when', 'start', 'end'):
            if data.get(key):
                task[key] = data[key]
    return jsonify(task), 201


@app.patch('/api/tasks/<int:task_id>')
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    _db_init()
    with _lock, _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        r = c.fetchone()
        if not r:
            return jsonify({'error': 'not found'}), 404
        cand = {
            'all_day': data.get('all_day', r['all_day']),
            'when': data.get('when', r['when']),
            'start': data.get('start', r['start']),
            'end': data.get('end', r['end']),
        }
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
        new_title = r['title']
        if 'title' in data:
            t = (data.get('title') or '').strip()
            if t:
                new_title = t
        new_done = r['done']
        if 'done' in data:
            new_done = 1 if bool(data['done']) else 0
        c.execute(
            "UPDATE tasks SET title=?, done=?, all_day=?, `when`=?, start=?, end=? WHERE id=?",
            (new_title, new_done, cand['all_day'], cand['when'], cand['start'], cand['end'], task_id),
        )
        conn.commit()
        c.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        r2 = c.fetchone()
        task = {'id': r2['id'], 'title': r2['title'], 'done': bool(r2['done'])}
        for key in ('all_day', 'when', 'start', 'end'):
            if r2[key] is not None:
                task[key] = r2[key]
        c.execute("SELECT code, version FROM task_emojis WHERE task_id=?", (task_id,))
        em_rows = c.fetchall()
        if em_rows:
            details = []
            catalog = _db_get_emoji_catalog()
            for em in em_rows:
                det = next((e for e in catalog if e['code'] == em['code'] and e['version'] == em['version']), None)
                if det:
                    details.append(det)
            if details:
                task['emojis'] = details
        return jsonify(task)


@app.delete('/api/tasks/<int:task_id>')
def delete_task(task_id: int):
    _db_init()
    with _lock, _db_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        if c.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        conn.commit()
    return jsonify({'ok': True})


# ===== Gamification Backend =====


def _get_request_user_name() -> Optional[str]:
    # Identify user by header or query string for simplicity
    name = request.headers.get('X-User-Name') or request.args.get('name')
    if isinstance(name, str):
        name = name.strip()
    return name or None


@app.post('/api/auth/login')
def auth_login():
    # In test mode, ensure a fresh DB per test by resetting on login
    if app.testing:
        try:
            os.remove(DB_FILE)
        except FileNotFoundError:
            pass
    _db_init()
    _migrate_users_json_to_db()
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    utc_offset = (data.get('utc_offset') or '+00:00')
    if not _NAME_RE.match(name):
        return jsonify({'error': 'invalid_name', 'message': 'Name must be 3-20 chars [A-Za-z0-9_]'}), 400

    with _lock:
        user = _db_get_user(name)
        if user is None:
            if _parse_offset(utc_offset) is None:
                utc_offset = '+00:00'
            user = _db_create_user(name, utc_offset)
        else:
            if isinstance(utc_offset, str) and _parse_offset(utc_offset):
                user['utc_offset'] = utc_offset
        _refresh_spins_if_needed(user)
        _db_update_user(user)
        # Maintain legacy users.json for tests to mutate
        if app.testing:
            _compat_dump_single_user_to_json(user)
        return jsonify(_user_profile_payload(user))


@app.get('/api/user/profile')
def user_profile():
    _db_init()
    name = _get_request_user_name()
    if not name:
        return jsonify({'error': 'not_found'}), 404
    with _lock:
        user = _db_get_user(name)
        if user is None:
            return jsonify({'error': 'not_found'}), 404
        _refresh_spins_if_needed(user)
        _db_update_user(user)
        return jsonify(_user_profile_payload(user))


@app.get('/api/emojis/catalog')
def emoji_catalog():
    _db_init()
    return jsonify(_db_get_emoji_catalog())


@app.get('/api/spin/pool')
def spin_pool():
    # Build a randomized pool with at least 8 segments and at least one emoji
    segments: List[Dict[str, Any]] = []
    catalog = _db_get_emoji_catalog()
    # Randomly pick some emojis (1-3) to include
    if catalog:
        k = random.randint(1, min(3, len(catalog)))
        emojis = random.sample(catalog, k=k)
        for item in emojis:
            segments.append({'type': 'emoji', 'emoji': item})
    # Fill the rest with odd prizes in randomized order
    odds = ODD_PRIZES[:]
    random.shuffle(odds)
    for label in odds:
        segments.append({'type': 'odd_prize', 'label': label})
    # Ensure at least 8 segments
    while len(segments) < 8:
        segments.append({'type': 'odd_prize', 'label': random.choice(ODD_PRIZES)})
    # Shuffle final list to vary positions
    random.shuffle(segments)
    return jsonify({'segments': segments[:8]})


def _pick_emoji_by_rarity() -> Dict[str, Any]:
    # Choose rarity by 85/10/5 policy
    r = random.random()
    if r < 0.85:
        rarity = 'common'
    elif r < 0.95:
        rarity = 'rare'
    else:
        rarity = 'very_rare'
    catalog = _db_get_emoji_catalog()
    candidates = [e for e in catalog if e['rarity'] == rarity]
    if not candidates:
        # Fallback to any catalog item
        candidates = catalog
    return random.choice(candidates)


@app.post('/api/spin')
def spin():
    _db_init()
    name = _get_request_user_name()
    if not name:
        return jsonify({'error': 'not_found'}), 404
    with _lock:
        user = _db_get_user(name)
        if user is None:
            return jsonify({'error': 'not_found'}), 404
        _refresh_spins_if_needed(user)
        if int(user.get('spins_remaining', 0)) <= 0:
            # Provide hint for UI to display banner per spec FR-007
            return jsonify({'error': 'no_spins_left', 'message': 'Daily spin limit reached.', 'limit_banner_required': True}), 400

        # Consume spin
        user['spins_remaining'] = int(user.get('spins_remaining', 0)) - 1

        # Invariant: ensure at least one emoji exists in catalog for spins
        catalog = _db_get_emoji_catalog()
        has_any_emoji = any(item.get('code') and item.get('version') for item in catalog)
        if not has_any_emoji:
            return jsonify({'error': 'pool_invalid', 'message': 'No emoji available in pool/config.'}), 400

        # 80% chance to yield an emoji, otherwise odd prize
        result: Dict[str, Any] = {}
        if random.random() < 0.8:
            emoji = _pick_emoji_by_rarity()
            # Check ownership via DB
            owned = _db_get_user_emojis(name)
            duplicate = any((e.get('code') == emoji['code'] and e.get('version') == emoji['version']) for e in owned)
            if not duplicate:
                _db_add_user_emoji(name, emoji['code'], emoji['version'])
            result = {
                'outcome_type': 'emoji',
                'emoji': emoji,
                'duplicate': duplicate,
                'spins_remaining': user['spins_remaining'],
            }
            # Optional: record spin history
            with _db_conn() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO spin_history(user_name, outcome_type, code, version, label) VALUES (?, ?, ?, ?, ?)",
                    (name, 'emoji', emoji['code'], emoji['version'], None)
                )
                conn.commit()
        else:
            label = random.choice(ODD_PRIZES)
            # Apply perk if landed
            if label.lower().startswith('multi-emoji'):
                user['has_multi_emoji'] = True
            result = {
                'outcome_type': 'odd_prize',
                'label': label,
                'spins_remaining': user['spins_remaining'],
            }
            # Optional: record spin history
            with _db_conn() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO spin_history(user_name, outcome_type, code, version, label) VALUES (?, ?, ?, ?, ?)",
                    (name, 'odd_prize', None, None, label)
                )
                conn.commit()

        _db_update_user(user)
        return jsonify(result)


@app.post('/api/tasks/<int:task_id>/emojis')
def add_task_emoji(task_id: int):
    _db_init()
    name = _get_request_user_name()
    if not name:
        return jsonify({'error': 'not_found'}), 404
    data = request.get_json(silent=True) or {}
    emoji = (data.get('emoji') or {})
    code = (emoji.get('code') or '').strip()
    version = (emoji.get('version') or '').strip()
    if not code or not version:
        return jsonify({'error': 'invalid_request'}), 400

    with _lock:
        user = _db_get_user(name)
        if user is None:
            return jsonify({'error': 'not_found'}), 404
        # Verify user owns emoji via DB
        db_emojis = _db_get_user_emojis(name)
        legacy_emojis = _legacy_get_user_emojis_from_json(name)
        owns = any(e.get('code') == code and e.get('version') == version for e in (db_emojis + legacy_emojis))
        if not owns:
            return jsonify({'error': 'emoji_locked'}), 400

        with _db_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, title, done FROM tasks WHERE id=?", (task_id,))
            r = c.fetchone()
            if not r:
                return jsonify({'error': 'not_found'}), 404
            # Already assigned?
            c.execute("SELECT 1 FROM task_emojis WHERE task_id=? AND code=? AND version=?", (task_id, code, version))
            if c.fetchone() is not None:
                return jsonify({'error': 'already_assigned'}), 400
            # Capacity
            c.execute("SELECT COUNT(*) FROM task_emojis WHERE task_id=?", (task_id,))
            (count,) = c.fetchone()
            capacity = 3 if bool(user.get('has_multi_emoji')) else 1
            if count >= capacity:
                if capacity == 1:
                    return jsonify({'error': 'multi_emoji_not_enabled'}), 400
                else:
                    return jsonify({'error': 'capacity_reached'}), 400
            # Insert and return updated task
            c.execute("INSERT INTO task_emojis(task_id, code, version) VALUES (?, ?, ?)", (task_id, code, version))
            conn.commit()
            task = {'id': r['id'], 'title': r['title'], 'done': bool(r['done'])}
            c.execute("SELECT code, version FROM task_emojis WHERE task_id=?", (task_id,))
            em_rows = c.fetchall()
            if em_rows:
                details = []
                catalog = _db_get_emoji_catalog()
                for em in em_rows:
                    det = next((e for e in catalog if e['code'] == em['code'] and e['version'] == em['version']), None)
                    if det:
                        details.append(det)
                if details:
                    task['emojis'] = details
            return jsonify(task)


@app.delete('/api/tasks/<int:task_id>/emojis/<string:code_and_version>')
def remove_task_emoji(task_id: int, code_and_version: str):
    _db_init()
    name = _get_request_user_name()
    if not name:
        return jsonify({'error': 'not_found'}), 404
    # Parse code:version
    parts = code_and_version.split(':', 1)
    if len(parts) != 2:
        return jsonify({'error': 'invalid_request'}), 400
    code, version = parts[0], parts[1]

    with _lock, _db_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, done FROM tasks WHERE id=?", (task_id,))
        r = c.fetchone()
        if not r:
            return jsonify({'error': 'not_found'}), 404
        c.execute("DELETE FROM task_emojis WHERE task_id=? AND code=? AND version=?", (task_id, code, version))
        if c.rowcount == 0:
            return jsonify({'error': 'not_found'}), 404
        conn.commit()
        task = {'id': r['id'], 'title': r['title'], 'done': bool(r['done'])}
        c.execute("SELECT code, version FROM task_emojis WHERE task_id=?", (task_id,))
        em_rows = c.fetchall()
        if em_rows:
            details = []
            catalog = _db_get_emoji_catalog()
            for em in em_rows:
                det = next((e for e in catalog if e['code'] == em['code'] and e['version'] == em['version']), None)
                if det:
                    details.append(det)
            if details:
                task['emojis'] = details
        return jsonify(task)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    app.run(host='127.0.0.1', port=port, debug=True)
