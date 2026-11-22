import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp_server"))
from diff_scan import API1_LIMIT, DiffError, scan_diff_text  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_training_diff_is_ok() -> None:
    result = scan_diff_text((SAMPLES / "training_pr.diff").read_text())
    assert result["verdict"] == "ok"
    assert result["files"] == ["app/review_service.py", "app/api.py"]
    assert result["secrets"] == []


def test_sec1_secret_reported_with_line() -> None:
    result = scan_diff_text((SAMPLES / "with_secret.diff").read_text())
    assert result["verdict"] == "blocked"
    assert result["secrets"][0]["file"] == "app/settings.py"
    assert result["secrets"][0]["line"] == 3
    assert "ghp_" not in result["secrets"][0]["snippet"]


def test_api1_limit_exceeded() -> None:
    body = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -0,0 +1 @@\n+" + "x" * API1_LIMIT
    result = scan_diff_text(body)
    assert result["within_api1_limit"] is False
    assert result["verdict"] == "blocked"


def test_not_a_diff_rejected() -> None:
    with pytest.raises(DiffError):
        scan_diff_text("hello, this is not a diff")
