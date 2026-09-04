"""The widget is served as static ES modules from the same origin as the API.

If /widget stops being mounted the page still loads and merely renders nothing —
a silent failure, so it gets a test.
"""
from fastapi.testclient import TestClient

from helpmate import app as app_mod


def test_index_serves_the_demo_site():
    c = TestClient(app_mod.app)
    r = c.get("/")
    assert r.status_code == 200
    assert "widget/index.js" in r.text


def test_widget_modules_are_mounted():
    c = TestClient(app_mod.app)
    for path in ("/widget/index.js", "/widget/api.js",
                 "/widget/ui.js", "/widget/style.css"):
        assert c.get(path).status_code == 200, path
