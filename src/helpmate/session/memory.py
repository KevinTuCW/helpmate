"""History-aware query rewrite for multi-turn — pure and rule-based (no LLM call).

When a follow-up question leans on anaphora (它/这个/那款/上面…) or is too short to
retrieve on its own, we prepend the most recent user turn(s) so retrieval sees the
referent. This gives multi-turn coreference without paying for a second thinking-model
call — the enriched string is used only as the *retrieval* query; generation still
answers the user's actual words.
"""
import re

# Pronouns / anaphora that signal the question depends on earlier turns.
_ANAPHORA = re.compile(
    r"(它们?|他们?|她们?|这个|那个|这款|那款|这些|那些|这项|那项|该款?|"
    r"上面|前面|刚才|之前|上述|这条|那条|它的|他的)"
)


def needs_context(question: str, short_len: int = 6) -> bool:
    """True if the question likely needs prior turns to be retrievable on its own."""
    q = question.strip()
    return bool(_ANAPHORA.search(q)) or len(q) <= short_len


def rewrite_query(question: str, history: list[dict], max_turns: int = 2) -> str:
    """Prepend recent user turns when the current question needs context.

    history: list of {"role": "user"|"assistant", "content": str}, oldest→newest.
    Returns the original question unchanged when no context is needed or none exists.
    """
    if not history or not needs_context(question):
        return question
    prior_user = [h["content"] for h in history if h.get("role") == "user"]
    prior_user = [c for c in prior_user[-max_turns:] if c.strip()]
    if not prior_user:
        return question
    return " ".join(prior_user) + " " + question
