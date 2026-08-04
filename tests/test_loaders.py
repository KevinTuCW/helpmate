from helpmate.ingest.loaders import clean_html, table_to_markdown


def test_clean_html_keeps_main_drops_chrome():
    html = ("<html><head><style>.x{}</style></head><body>"
            "<nav>menu</nav><main><h1>DJI Care</h1>"
            "<p>Covers accidental damage.</p></main>"
            "<footer>foot</footer></body></html>")
    out = clean_html(html)
    assert "DJI Care" in out and "Covers accidental damage." in out
    assert "menu" not in out and "foot" not in out and ".x{}" not in out


def test_table_to_markdown():
    rows = [["Model", "Weight"], ["Mini 4 Pro", "249g"]]
    assert table_to_markdown(rows) == (
        "| Model | Weight |\n| --- | --- |\n| Mini 4 Pro | 249g |"
    )
