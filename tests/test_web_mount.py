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
    assert "widget/index.js?v=demo-customer-1" in r.text


def test_widget_modules_are_mounted():
    c = TestClient(app_mod.app)
    for path in ("/widget/index.js", "/widget/api.js",
                 "/widget/ui.js", "/widget/style.css"):
        assert c.get(path).status_code == 200, path


def test_widget_supports_local_demo_customer_url():
    c = TestClient(app_mod.app)
    index = c.get("/widget/index.js").text
    assert "localDemoIdentity" in index
    assert "C-(00[1-9]|010)" in index
    assert "sim-${customer.toLowerCase()" in index
    assert "localhost" in index
    assert ": 'C-001'" in index


def test_offer_controls_support_english_conversations():
    c = TestClient(app_mod.app)
    ui = c.get("/widget/ui.js").text
    index = c.get("/widget/index.js").text
    assert "I still want to return it" in ui
    assert "Processing…" in ui
    assert "Accepted" in ui
    assert "onDecline: (message) => ask(message)" in index
