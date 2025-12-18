import pathlib


def test_frontend_homepage_contains_hero():
    root = pathlib.Path(__file__).resolve().parents[1]
    # file lives at ../frontend/index.html relative to backend/tests
    front = root / 'frontend' / 'index.html'
    assert front.exists(), f"frontend/index.html not found at {front}"
    txt = front.read_text(encoding='utf-8')
    assert '<h2>Welcome to SmartFly' in txt
    assert 'id="homePanel"' in txt
