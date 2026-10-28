from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_demo_state_script_contains_atomic_validation_and_versioned_state() -> None:
    source = (ROOT / "static/js/demo-state.js").read_text()
    assert "contract_version" not in source  # state producers define the demo-specific versioned payload
    assert "structuredClone" in source
    assert "normalize" in source
    assert "VALIDATION_ERROR" in source


def test_chebyshev_demo_uses_node_count_vocabulary() -> None:
    source = (ROOT / "static/js/demos/chebyshev.js").read_text()
    assert "node_count" in source
    assert "createDemoState" in source
