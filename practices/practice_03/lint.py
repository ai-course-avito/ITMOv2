import os
import subprocess
import sys


def ensure_ruff() -> str:
    """Return module name if available; otherwise, bootstrap via pipx fallback."""
    try:
        import ruff  # noqa: F401
        return 'ruff'
    except ImportError:
        # Fallback: try pipx, then venv-local install
        pipx = subprocess.run(['which', 'pipx'], capture_output=True, text=True, check=False)
        if pipx.returncode == 0:
            subprocess.check_call(['pipx', 'install', 'ruff'], stdout=subprocess.DEVNULL)
            return 'ruff'
        # Create a local venv in practices/practice_03/.venv and install ruff there
        venv_dir = os.path.join(os.path.dirname(__file__), '.venv')
        if not os.path.isdir(venv_dir):
            subprocess.check_call([sys.executable, '-m', 'venv', venv_dir])
        python_bin = os.path.join(venv_dir, 'bin', 'python')
        subprocess.check_call([python_bin, '-m', 'pip', 'install', 'ruff'])
        return python_bin + ' -m ruff'


def main() -> int:
    runner = ensure_ruff()
    # First auto-fix, then check; exclude lab/** to respect demo boundaries
    fix_cmd = runner.split() + ['check', '--fix', '--exclude', 'lab/**', '.']
    print('Running', ' '.join(fix_cmd))
    subprocess.call(fix_cmd)
    check_cmd = runner.split() + ['check', '--exclude', 'lab/**', '.']
    print('Running', ' '.join(check_cmd))
    return subprocess.call(check_cmd)


if __name__ == '__main__':
    sys.exit(main())
