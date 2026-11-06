import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Добавляем backend/ в sys.path, чтобы работал импорт `from app.main import app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.leaderboard import LeaderboardStore  # noqa: E402
from app.main import app, get_store  # noqa: E402


class FakeClock:
    """Подменяемые часы: время стоит, пока тест не сдвинет его через advance()."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(tmp_path, clock) -> LeaderboardStore:
    return LeaderboardStore(tmp_path / "leaderboard.json", clock=clock.now)


@pytest.fixture
def client(store):
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
