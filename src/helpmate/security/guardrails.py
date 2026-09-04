"""Rules-based input/output guardrails — pure, no LLM call, so zero latency cost.

The input guard stops prompt-injection / jailbreak / privilege-escalation attempts
*before* they reach the model; the output guard redacts leaked secrets and blocks
disallowed content *before* a reply leaves the system. Both are deterministic and
unit-tested. This is the "敢上线" layer on top of the "能答" baseline — deliberately
cheap and explainable rather than a second thinking-model call.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

REFUSAL_INPUT = "抱歉，这个请求我无法处理。我只能回答与产品知识库和你自己的订单/物流相关的问题。"
REFUSAL_OUTPUT = "抱歉，我这次无法给出合规的回答，请换个问法或联系人工客服。"

# --- input: prompt injection / instruction override -------------------------
_INJECTION = [
    re.compile(r"(?i)ignore\s+(all\s+|the\s+)?(previous|above|prior)\s+(instructions|prompts?)"),
    re.compile(r"(?i)disregard\s+(the\s+)?(above|previous|system)"),
    re.compile(r"(?i)(reveal|show|print|repeat|leak)\s+(me\s+)?(your\s+)?(system\s+)?(prompt|instructions)"),
    re.compile(r"忽略(掉)?(以上|上面|之前|前面|所有).{0,6}(指令|提示|规则|设定)"),
    re.compile(r"(泄露|告诉我|输出|打印|复述).{0,6}(系统)?(提示词|提示语|系统提示|prompt)"),
    re.compile(r"你的(系统)?(提示词|设定|指令)是(什么|啥)"),
]

# --- input: jailbreak / role-play to shed restrictions ----------------------
_JAILBREAK = [
    re.compile(r"(?i)\b(DAN|do anything now|developer mode|jailbreak)\b"),
    re.compile(r"(?i)act\s+as\s+.{0,40}(no\s+restrictions|without\s+restrictions|unfiltered)"),
    re.compile(r"(开发者|上帝|无限制)模式"),
    re.compile(r"(无视|绕过|突破|解除).{0,6}(所有)?(限制|规则|安全|审查)"),
    re.compile(r"假装你(是|没有).{0,10}(限制|规则|约束)"),
    re.compile(r"越狱"),
]

# --- input: privilege escalation / cross-tenant data probing ----------------
_ESCALATION = [
    re.compile(r"(?i)\b(select|drop|delete|update|insert)\b.{0,20}\b(from|table|into)\b"),
    re.compile(r"(?i)(dump|list|show)\s+(all\s+)?(orders|customers|users|tables|data)"),
    re.compile(r"(所有|全部|别人|他人|其他)(人|用户|客户)的?(订单|物流|信息|数据|资料)"),
    re.compile(r"(列出|导出|查看|给我).{0,6}(所有|全部)(订单|客户|用户)"),
    re.compile(r"别人的(订单|物流|账号|信息)"),
]

# --- output: secrets that must never appear in a reply ----------------------
_SECRET = [
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key|password)\s*[:=]\s*\S+"),
    re.compile(r"postgres(ql)?://[^\s]+"),
]

# --- PII that must not land in the audit trail in the clear -----------------
_PII = [
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),                  # CN mobile
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),                   # email
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),                 # CN id card
    re.compile(r"(?<!\d)\d{16,19}(?!\d)"),                    # bank card
]

# --- output: hard-blocked disallowed content --------------------------------
_BANNED = [
    re.compile(r"(制作|制造|如何(制作|制造)).{0,10}(炸弹|爆炸物|毒品|枪支)"),
    re.compile(r"(?i)how\s+to\s+(make|build).{0,10}(bomb|explosive|weapon)"),
]


@dataclass
class GuardResult:
    """Verdict from a guardrail. `text` carries the (possibly redacted) content."""
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    text: str = ""

    @property
    def blocked(self) -> bool:
        return not self.allowed


def _match_any(text: str, label: str, patterns: list[re.Pattern]) -> list[str]:
    return [label] if any(p.search(text) for p in patterns) else []


def check_input(text: str) -> GuardResult:
    """Screen a user question. Blocks injection / jailbreak / privilege escalation."""
    reasons: list[str] = []
    reasons += _match_any(text, "prompt_injection", _INJECTION)
    reasons += _match_any(text, "jailbreak", _JAILBREAK)
    reasons += _match_any(text, "privilege_escalation", _ESCALATION)
    return GuardResult(allowed=not reasons, reasons=reasons, text=text)


def redact_pii(text: str) -> str:
    """Mask secrets and personal identifiers before persistence.

    The audit trail already stores an answer *hash* instead of the answer, but
    the question was going in verbatim — and a support question is exactly where
    a phone number or an email shows up. Same treatment, both directions.
    """
    if not text:
        return text
    out = text
    for p in _SECRET + _PII:
        out = p.sub("***", out)
    return out


def check_output(text: str) -> GuardResult:
    """Screen a generated answer: hard-block disallowed content, redact secrets.

    Disallowed content → blocked (empty text). A leaked secret → allowed but
    redacted, and flagged in `reasons` so the audit trail records the near-miss.
    """
    if _match_any(text, "disallowed_content", _BANNED):
        return GuardResult(allowed=False, reasons=["disallowed_content"], text="")
    reasons: list[str] = []
    sanitized = text
    for p in _SECRET:
        if p.search(sanitized):
            reasons.append("secret_leak")
            sanitized = p.sub("***", sanitized)
    return GuardResult(allowed=True, reasons=reasons, text=sanitized)


# --- output: the streaming variant -------------------------------------------
_SENTENCE_END = re.compile(r"[。！？!?\n]")


class StreamGuard:
    """Guards an answer that is being streamed token by token.

    Text is held until a sentence boundary, redacted, then released. The real
    `check_output` verdict only exists once the answer is complete, so a hard
    block surfaces from `finish()` and the transport replaces what was shown.

    Known residual risk: a secret straddling a flush boundary could be released
    in fragments. In practice secrets contain no 。！？ so a sentence-boundary
    flush cannot split one; `finish()` re-checks the full text either way, so the
    audit trail still records `secret_leak` even in that case.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._sent = ""
        self.reasons: list[str] = []

    def feed(self, delta: str) -> Optional[str]:
        """Buffer a token. Returns text to emit once at least one sentence closed."""
        self._buf += delta
        last = None
        for last in _SENTENCE_END.finditer(self._buf):
            pass
        if last is None:
            return None
        cut = last.end()
        chunk, self._buf = self._buf[:cut], self._buf[cut:]
        return self._release(chunk)

    def finish(self) -> tuple[str, GuardResult]:
        """Flush the tail and rule on the whole answer.

        Returns `(tail_to_emit, verdict)`. When `verdict.blocked`, the client must
        replace everything already shown with `verdict.text`.
        """
        tail = self._release(self._buf) if self._buf else ""
        self._buf = ""
        verdict = check_output(self._sent)
        if verdict.blocked:
            return tail, GuardResult(allowed=False, reasons=verdict.reasons,
                                     text=REFUSAL_OUTPUT)
        reasons = list(dict.fromkeys(self.reasons + verdict.reasons))
        return tail, GuardResult(allowed=True, reasons=reasons, text=self._sent)

    def _release(self, chunk: str) -> str:
        for p in _SECRET:
            if p.search(chunk):
                if "secret_leak" not in self.reasons:
                    self.reasons.append("secret_leak")
                chunk = p.sub("***", chunk)
        self._sent += chunk
        return chunk
