"""Question suggestions — three moments, three very different budgets.

Opening "hot" questions and typeahead both read one *question bank* (a hand-written
seed list plus this tenant's own PII-redacted audit trail) and cost a single indexed
query. Post-answer follow-ups cost one small-model call, made after the answer is
already on screen so it never delays the reply.

The bank is not built on full-text search on purpose: `chunks.content_tsv` uses
Postgres' `simple` parser, which does not segment Chinese — a whole sentence
collapses into one token, so `websearch_to_tsquery('simple','限飞')` matches
nothing. `ILIKE` over a few hundred short questions needs no segmentation at all.
"""
import re

from helpmate import db

# Cold-start fallback, one per corpus type (faq / policy / manual / order) so a
# fresh install still opens with something worth clicking.
SEED_QUESTIONS = [
    "Mini 4 Pro 的续航和图传距离是多少",
    "限飞区怎么申请解禁",
    "整机保修范围包不包括炸机",
    "怎么查询我的订单物流状态",
    "电池长期存放要注意什么",
    "固件升级失败了怎么办",
]

MIN_PREFIX = 2   # one Chinese character matches almost everything — not a hint

FOLLOWUP_PROMPT = (
    "你是客服助手。根据下面这轮问答，写出用户接下来最可能问的 3 个问题。\n"
    "要求：每行一个问题；不加序号、编号和任何前缀；每个不超过 20 字；"
    "必须能用同一个知识库回答；不要重复用户已经问过的问题。\n\n"
    "用户问：{question}\n客服答：{answer}\n参考文档：{titles}\n\n三个问题："
)

MAX_FOLLOWUP_LEN = 20            # longer than this reads like a paragraph, not a chip
_LEAD = re.compile(r"^\s*(\d+\s*[.、)）]|[-*·•]|Q\d*\s*[:：])\s*")


def hot_questions(tenant_id: str, limit: int = 4, days: int = 7) -> list[str]:
    """Opening suggestions: this tenant's real traffic first, seeds to fill up."""
    try:
        asked = db.top_questions(tenant_id, days=days, limit=limit)
    except Exception:
        asked = []
    out = list(dict.fromkeys(asked))
    for q in SEED_QUESTIONS:
        if len(out) >= limit:
            break
        if q not in out:
            out.append(q)
    return out[:limit]


def match_questions(prefix: str, tenant_id: str, limit: int = 5) -> list[str]:
    """Typeahead: past questions containing what the user has typed so far."""
    p = prefix.strip()
    if len(p) < MIN_PREFIX:
        return []
    try:
        hist = db.search_questions(p, tenant_id, limit=limit)
    except Exception:
        hist = []
    out = list(dict.fromkeys(hist))
    for q in SEED_QUESTIONS:
        if len(out) >= limit:
            break
        if p in q and q not in out:
            out.append(q)
    return out[:limit]


def followups(question: str, answer: str, hit_titles: list[str], llm,
              limit: int = 3) -> list[str]:
    """Post-answer follow-ups from the small model. Never raises."""
    if not answer.strip():
        return []
    prompt = FOLLOWUP_PROMPT.format(
        question=question,
        answer=answer[:600],                       # the tail rarely changes what to ask next
        titles="、".join(hit_titles[:4]) or "无",
    )
    try:
        raw = llm.complete_small(prompt)
    except Exception:
        return []
    return clean_followups(raw, question, limit)


def clean_followups(raw: str, question: str, limit: int = 3) -> list[str]:
    """Turn a small model's free-form reply into at most `limit` clickable chips.

    Anything doubtful is dropped rather than repaired: showing two good chips
    beats showing three with one piece of garbage in it.
    """
    asked = question.strip()
    out: list[str] = []
    for line in (raw or "").splitlines():
        q = _LEAD.sub("", line).strip().strip("“”\"'")
        if not q or len(q) > MAX_FOLLOWUP_LEN:
            continue
        if q.endswith(("：", ":")):                  # "以下是三个问题：" and friends
            continue
        if q == asked or q in out:
            continue
        out.append(q)
        if len(out) >= limit:
            break
    return out
