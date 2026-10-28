from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_shared_assets_and_preference_contract_exist():
    assert (ROOT / "static/css/tokens.css").exists()
    assert (ROOT / "static/css/site.css").exists()
    prefs = (ROOT / "static/js/prefs.js").read_text()
    assert "ui:preferences:v1" in prefs
    assert "gradientIntensity" in prefs
    assert "reducedMotion" in prefs
