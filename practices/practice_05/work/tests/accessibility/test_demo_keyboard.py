from pathlib import Path


def test_fourier_demo_declares_keyboard_controls():
    html = (Path(__file__).resolve().parents[2] / "fourier/index.html").read_text()
    assert 'aria-label="Воспроизвести"' in html
    assert 'aria-label="Шаг вперёд"' in html
    assert "ArrowRight" in html
    assert "ArrowLeft" in html
