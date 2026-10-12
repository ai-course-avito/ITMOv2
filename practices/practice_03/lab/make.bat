@echo off
if "%1"=="test" (
    python -m unittest discover -s "%~dp0demo" -v
) else if "%1"=="install" (
    python -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print('Standard library only: ready')"
) else (
    python -m unittest discover -s "%~dp0demo" -v
)
