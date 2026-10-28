from pathlib import Path


def test_shared_styles_define_responsive_and_reduced_motion_behavior():
    css = (Path(__file__).resolve().parents[2] / "static/css/site.css").read_text()
    assert "min-width: 640px" in css
    assert "prefers-reduced-motion" in css
    assert "focus-visible" in css
