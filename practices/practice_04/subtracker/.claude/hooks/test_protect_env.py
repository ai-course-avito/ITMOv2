import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).with_name("protect_env.py")


def run_hook(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True
    )


def payload(tool: str, file_path: str) -> str:
    return json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path}})


@pytest.mark.parametrize(
    "path",
    ["/p/backend/.env", ".env", "/p/.env.local", "/p/.env.production"],
)
@pytest.mark.parametrize("tool", ["Write", "Edit"])
def test_secret_files_are_blocked(tool, path):
    result = run_hook(payload(tool, path))
    assert result.returncode == 2
    assert "BLOCKED" in result.stderr
    assert path in result.stderr


@pytest.mark.parametrize(
    "path",
    [
        "/p/backend/.env.example",
        "/p/.env.sample",
        "/p/backend/app/main.py",
        "/p/environment.md",
        "/p/backend/envs/readme.txt",
    ],
)
def test_other_files_are_allowed(path):
    result = run_hook(payload("Edit", path))
    assert result.returncode == 0
    assert result.stderr == ""


def test_payload_without_file_path_is_allowed():
    result = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
    assert result.returncode == 0


def test_malformed_input_does_not_block_work():
    assert run_hook("not json").returncode == 0


def bash_payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


@pytest.mark.parametrize(
    "command",
    [
        "echo 'DEBUG=true' >> backend/.env",
        "printf 'A=1\\n' > .env",
        "echo x | tee -a backend/.env",
        "sed -i '' 's/a/b/' backend/.env",
        "cp backend/.env.example backend/.env",
        "mv .env.local .env.bak",
        "rm backend/.env",
        "truncate -s 0 backend/.env",
        "python3 -c \"open('backend/.env','a').write('X=1')\"",
        "cd backend && echo DEBUG=true>>.env",
    ],
)
def test_bash_writes_to_secret_files_are_blocked(command):
    result = run_hook(bash_payload(command))
    assert result.returncode == 2
    assert "BLOCKED" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "cat backend/.env",
        "grep -c KEY backend/.env 2>/dev/null",
        "git check-ignore -v backend/.env",
        "echo 'DEBUG=false' >> backend/.env.example",
        "ls -la backend",
        "uv run pytest -q",
        "echo hello > notes.txt",
    ],
)
def test_bash_reads_and_other_files_are_allowed(command):
    result = run_hook(bash_payload(command))
    assert result.returncode == 0
    assert result.stderr == ""
