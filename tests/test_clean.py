from helpmate.ingest.clean import (
    strip_boilerplate, dedupe_repeated_lines, clean_corpus_text,
)


def test_strip_boilerplate_drops_chrome():
    text = "首页\n登录\nMini 3 Pro 续航约 34 分钟。\n版权所有 © DJI\n京ICP备12345号"
    out = strip_boilerplate(text)
    assert "Mini 3 Pro 续航约 34 分钟。" in out
    assert "首页" not in out and "版权所有" not in out and "京ICP备" not in out


def test_strip_collapses_blank_runs():
    assert strip_boilerplate("a\n\n\n\nb") == "a\n\nb"


def test_dedupe_repeated_lines():
    text = "\n".join(["返回顶部", "正文一", "返回顶部", "正文二", "返回顶部"])
    out = dedupe_repeated_lines(text, min_repeats=3)
    assert "返回顶部" not in out
    assert "正文一" in out and "正文二" in out


def test_dedupe_keeps_repeated_long_lines():
    long = "这是一段很长的正文内容会重复出现但不属于导航噪声所以应当保留下来"
    text = "\n".join([long, long, long])
    assert long in dedupe_repeated_lines(text, min_repeats=3)


def test_clean_corpus_text_combines():
    text = "关注我们\nMini 4 Pro 参数表\n关注我们\n实际内容\n关注我们"
    out = clean_corpus_text(text)
    assert "关注我们" not in out and "实际内容" in out
