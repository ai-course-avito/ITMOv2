import sys
from pathlib import Path

# Добавляем backend/ в sys.path, чтобы работал импорт `from app.main import app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
