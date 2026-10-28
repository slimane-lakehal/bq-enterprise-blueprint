"""
Stable hashing for reproducible synthetic data.

The builtin hash() on str is salted per process (PYTHONHASHSEED), so anything
derived from it changes between runs -- which silently breaks the idempotency
guarantee of a re-run. These helpers are stable across processes and machines.
"""

import hashlib


def stable_int(value: str) -> int:
    """Deterministic 32-bit integer for a string."""
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "big")
