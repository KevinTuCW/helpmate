"""Make Chinese reachable by PostgreSQL full-text search, without an extension.

`chunks.content_tsv` used to be `to_tsvector('simple', content)`. That produces
nothing usable for Chinese, and *how* it fails depends on the platform:

  macOS (en_US.UTF-8)  ts_debug classifies a Chinese run as `blank` → tsvector
                       is empty, every Chinese query matches 0 rows
  Debian / glibc       the whole run becomes one token → matches only if the
                       query happens to be that entire run, so also ~0 rows

The parser decides with `iswalpha()` against the database ctype, so no amount of
word segmentation fixes it on its own — a segmented Chinese word is still `blank`.
The proper fix is a CJK parser extension (zhparser / pg_jieba), but neither has a
Homebrew formula and the Docker image would need rebuilding, which puts the two
dev environments back out of sync.

So: segment with jieba, then map each non-ASCII word to an ASCII surrogate the
parser cannot reject. Latin and digit tokens pass through verbatim, because exact
matches on model names and specs ("Mini 4 Pro", "O4") are the one thing the FTS
leg was genuinely contributing before.

Documents and queries must go through the *same* function, or the index gets
populated with surrogates nothing will ever search for.
"""
import hashlib
import re

import jieba

_ASCII_WORD = re.compile(r"^[a-z0-9]+$")

# 8 hex characters over a few thousand distinct terms leaves collision odds
# around 1e-5 — cheaper than storing the full digest, and a collision merely
# means one extra candidate for the reranker to drop.
_SURROGATE_LEN = 8


def _surrogate(word: str) -> str:
    """ASCII stand-in for a non-ASCII word. Leading letter keeps it an asciiword."""
    return "z" + hashlib.md5(word.encode("utf-8")).hexdigest()[:_SURROGATE_LEN]


def _tokens(text: str):
    for raw in jieba.cut(text or ""):
        word = raw.strip().lower()
        if not word:
            continue
        if word.isascii():
            if _ASCII_WORD.match(word):      # drops punctuation and symbols
                yield word
        else:
            yield _surrogate(word)


def segment(text: str) -> str:
    """Space-joined, parser-safe tokens for indexing a document."""
    return " ".join(_tokens(text))


def segment_query(text: str) -> str:
    """Same transformation for a search query. Kept as a separate name so call
    sites read correctly; any divergence between the two would silently break
    retrieval rather than raise."""
    return segment(text)
