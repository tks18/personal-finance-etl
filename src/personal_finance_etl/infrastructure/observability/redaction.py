# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Observability privacy, redaction, and configuration fingerprinting engine.

Owns
----
- Key-based and pattern-based masking of credentials, tokens, PAN, and PII.
- Recursive redaction across arbitrary JSON-compatible dictionaries and event contexts.
- Deterministic cryptographic hashing of entity identifiers for anonymous correlation.
- Configuration fingerprinting preserving provenance without leaking secret parameters.

Does not own
-------------
- Forensic JSONL file persistence (owned by infrastructure.observability.forensic_sink).
- Settings TOML loading or validation (owned by config.settings).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from personal_finance_etl.config.settings import Settings

__all__ = [
    "SENSITIVE_KEY_SUBSTRINGS",
    "fingerprint_config",
    "hash_identifier",
    "redact_dict",
    "redact_text",
]

SENSITIVE_KEY_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "token",
        "credential",
        "api_key",
        "apikey",
        "access_token",
        "auth",
        "pin",
        "pan",
        "ssn",
        "account_number",
        "card_number",
        "iban",
        "cvv",
    }
)

_BEARER_TOKEN_REGEX = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]{15,}\b")
_CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_INDIAN_PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_US_SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_GENERIC_SECRET_ASSIGN_REGEX = re.compile(
    r"(?i)\b(api_key|token|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?"
)


def hash_identifier(value: str, prefix: str = "id_") -> str:
    """Compute a truncated deterministic SHA-256 hash for correlation without PII exposure.

    Parameters
    ----------
    value : str
        Sensitive identifier string (e.g. account number or user email).
    prefix : str, default='id_'
        Identifier prefix prepended to the hash digest.

    Returns
    -------
    str
        Truncated 10-character hex hash with prefix.
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}{digest}"


def redact_text(text: str) -> str:
    """Mask known sensitive patterns (Bearer tokens, card numbers, PAN, SSN) within text.

    Parameters
    ----------
    text : str
        Input string to sanitize.

    Returns
    -------
    str
        Sanitized text with masked secrets.
    """
    if not text:
        return text

    sanitized = _BEARER_TOKEN_REGEX.sub("Bearer [REDACTED_TOKEN]", text)
    sanitized = _GENERIC_SECRET_ASSIGN_REGEX.sub(r"\1=[REDACTED]", sanitized)
    sanitized = _INDIAN_PAN_REGEX.sub("[REDACTED_PAN]", sanitized)
    sanitized = _US_SSN_REGEX.sub("[REDACTED_SSN]", sanitized)
    sanitized = _CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", sanitized)
    return sanitized


def redact_dict(
    data: Mapping[Any, Any],
    depth: int = 0,
    max_depth: int = 8,
) -> dict[str, Any]:
    """Recursively scrub sensitive keys and patterns from a dictionary structure.

    Parameters
    ----------
    data : Mapping[Any, Any]
        Dictionary to sanitize.
    depth : int, default=0
        Current recursion depth.
    max_depth : int, default=8
        Recursion limit to prevent cyclic explosion.

    Returns
    -------
    dict[str, Any]
        Sanitized dictionary with masked sensitive fields.
    """
    if depth > max_depth:
        return {"_truncated": "max_recursion_depth"}

    redacted: dict[str, Any] = {}
    for raw_key, val in data.items():
        key = str(raw_key)
        key_lower = key.lower()
        if any(substr in key_lower for substr in SENSITIVE_KEY_SUBSTRINGS):
            redacted[key] = "[REDACTED]"
        elif isinstance(val, Mapping):
            redacted[key] = redact_dict(val, depth=depth + 1, max_depth=max_depth)
        elif isinstance(val, (list, tuple)):
            redacted_items: list[Any] = []
            for item in val:
                if isinstance(item, Mapping):
                    redacted_items.append(redact_dict(item, depth=depth + 1, max_depth=max_depth))
                elif isinstance(item, str):
                    redacted_items.append(redact_text(item))
                else:
                    redacted_items.append(item)
            redacted[key] = redacted_items
        elif isinstance(val, str):
            redacted[key] = redact_text(val)
        else:
            redacted[key] = val

    return redacted


def fingerprint_config(settings: Settings | Mapping[str, Any]) -> dict[str, Any]:
    """Generate a deterministic configuration fingerprint and privacy-safe metadata summary.

    Parameters
    ----------
    settings : Settings | Mapping[str, Any]
        Application settings instance or settings dictionary.

    Returns
    -------
    dict[str, Any]
        Dictionary containing config SHA-256 fingerprint and safe non-sensitive parameters.
    """
    if isinstance(settings, Settings):
        raw_dict = settings.model_dump(mode="python")
    else:
        raw_dict = dict(settings)

    # Compute deterministic hash over sorted canonical JSON
    canonical_json = json.dumps(raw_dict, sort_keys=True, default=str)
    config_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    safe_summary = {
        "config_hash": f"sha256_{config_hash[:16]}",
        "target_db_name": str(raw_dict.get("TARGET_DB_NAME", "")),
        "disable_file_discoverer": bool(raw_dict.get("DISABLE_FILE_DISCOVERER", False)),
        "retain_last_n_runs": int(raw_dict.get("RETAIN_LAST_N_RUNS", 12)),
        "logs_directory": str(raw_dict.get("LOGS_DIRECTORY", "logs/runs")),
    }
    return safe_summary
