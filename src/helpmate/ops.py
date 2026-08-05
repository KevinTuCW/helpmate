"""Small operational helpers. Pure and unit-tested."""
import hashlib


def should_sample(key: str, rate: int) -> bool:
    """Deterministic per-key sampling gate — True for ~`rate`% of distinct keys.

    Deterministic (hash of the key) so a given session is consistently sampled or
    not across its turns, rather than flickering request to request.
    """
    if rate <= 0:
        return False
    if rate >= 100:
        return True
    bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % 100
    return bucket < rate
