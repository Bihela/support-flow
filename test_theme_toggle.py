from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_homepage_has_theme_toggle():
    html = client.get("/").text
    assert 'id="themeToggle"' in html          # toggle button in header
    assert 'darkMode: "class"' in html          # tailwind dark mode enabled
    assert "/static/theme.js" in html           # persistence script loaded


def test_theme_script_persists_to_localstorage():
    js = client.get("/static/theme.js").text
    assert 'localStorage.setItem("theme"' in js
    assert 'localStorage.getItem("theme")' in js
