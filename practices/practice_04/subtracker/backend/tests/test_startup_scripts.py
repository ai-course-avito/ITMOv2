import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def run_python(args, cwd, env_overrides=None, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env.update(env_overrides or {})
    return subprocess.run(
        [sys.executable, *args],
        check=False,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def test_startup_fails_without_secret_key(tmp_path):
    # tmp_path has no env file, so the setting can only come from the environment.
    result = run_python(["-c", "import app.config"], cwd=tmp_path, drop=("SECRET_KEY",))
    assert result.returncode != 0
    assert "secret_key" in result.stderr.lower()


def test_check_db_reports_unreachable_database(tmp_path):
    result = run_python(
        ["-m", "scripts.check_db"],
        cwd=BACKEND_DIR,
        env_overrides={
            "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:1/none",
            "SECRET_KEY": "test-secret-key-with-sufficient-length-32b",
        },
    )
    assert result.returncode == 1
    assert "127.0.0.1:1" in result.stderr
