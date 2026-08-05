"""Boilerplate cleaning for ingest — strip nav/footer/legal chrome and repeated
lines before chunking, so retrieval isn't diluted by non-content. Pure and
deterministic; runs after HTML extraction, before section splitting.
"""
import re
from collections import Counter

_BOILERPLATE = [
    re.compile(r"^\s*(首页|登录|注册|购物车|返回顶部|回到顶部|下载\s*App|关注我们|"
               r"联系我们|意见反馈|扫码关注|分享到|上一页|下一页|更多)\s*$"),
    re.compile(r"^\s*(版权所有|保留所有权利|Copyright|©).*$", re.I),
    re.compile(r"^\s*(Cookie|隐私政策|使用条款|服务条款|Terms of Use|Privacy Policy|"
               r"All rights reserved).*$", re.I),
    re.compile(r"^\s*京ICP备.*$"),
]


def strip_boilerplate(text: str) -> str:
    """Drop obvious chrome lines and collapse runs of blank lines."""
    kept = [ln for ln in text.splitlines()
            if not any(p.match(ln) for p in _BOILERPLATE)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def dedupe_repeated_lines(text: str, min_repeats: int = 3, max_len: int = 20) -> str:
    """Remove short lines that repeat across the doc — a nav/footer fingerprint."""
    lines = text.splitlines()
    counts = Counter(ln.strip() for ln in lines if ln.strip())
    noise = {ln for ln, c in counts.items() if c >= min_repeats and len(ln) <= max_len}
    return "\n".join(ln for ln in lines if ln.strip() not in noise)


def clean_corpus_text(text: str) -> str:
    """Full cleaning pass: drop repeated chrome, then per-line boilerplate."""
    return strip_boilerplate(dedupe_repeated_lines(text))
