"""Observability privacy, redaction, and configuration fingerprinting engine.

Owns
----
- RedactionPolicy: Central privacy policies (SAFE, HASH, REDACT, OMIT).
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

import enum
import hashlib
import json
import re
from collections.abc import Mapping, Sequence, Sized
from typing import TypedDict, cast

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings

__all__ = [
    "ConfigFingerprintDict",
    "RedactionPolicy",
    "RulesFingerprintDict",
    "SENSITIVE_KEY_SUBSTRINGS",
    "fingerprint_config",
    "fingerprint_rules",
    "hash_identifier",
    "redact_dict",
    "redact_text",
]

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | Sequence["JsonValue"] | Mapping[str, "JsonValue"]


class ConfigFingerprintDict(TypedDict):
    """Deterministic configuration fingerprint and safe summary metadata.

    Attributes
    ----------
    config_hash : str
        Hex-encoded SHA-256 fingerprint prefix of the canonical configuration.
    target_db_name : str
        Target SQLite database filename.
    disable_file_discoverer : bool
        Flag indicating if automatic file discovery is disabled.
    retain_last_n_runs : int
        Number of previous run log directories retained on disk.
    logs_directory : str
        Target root directory path for execution logs.
    """

    config_hash: str
    target_db_name: str
    disable_file_discoverer: bool
    retain_last_n_runs: int
    logs_directory: str


class RulesFingerprintDict(TypedDict):
    """Deterministic financial rules fingerprint and safe summary metadata.

    Attributes
    ----------
    rules_hash : str
        Hex-encoded SHA-256 fingerprint prefix of the canonical rules configuration.
    default_currency_id : str
        Default active currency identifier.
    investment_instrument_count : int
        Number of configured investment instrument policy definitions.
    has_tax_assumptions : bool
        Flag indicating if tax calculation assumptions are configured.
    """

    rules_hash: str
    default_currency_id: str
    investment_instrument_count: int
    has_tax_assumptions: bool


class RedactionPolicy(enum.Enum):
    """Central privacy policy governing how telemetry fields and sensitive data are treated."""

    SAFE = "SAFE"
    HASH = "HASH"
    REDACT = "REDACT"
    OMIT = "OMIT"


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
        "authorization",
        "client_secret",
        "private_key",
        "pin",
        "pan",
        "ssn",
        "account_number",
        "card_number",
        "iban",
        "cvv",
        "jwt",
        "passwd",
        "pwd",
    }
)

_BEARER_TOKEN_REGEX = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]{15,}\b")
_GENERIC_SECRET_ASSIGN_REGEX = re.compile(
    r"(?i)\b(api_key|apikey|token|access_token|secret|password|passwd|pwd|credential)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?"
)
_JWT_TOKEN_REGEX = re.compile(
    r"(?<![A-Za-z0-9])eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}(?![A-Za-z0-9])"
)
_API_KEY_REGEX = re.compile(
    r"(?<![A-Za-z0-9])(?:sk_live|sk_test|pk_live|pk_test)_[A-Za-z0-9]{20,}(?![A-Za-z0-9])"
)
_GITHUB_TOKEN_REGEX = re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36}(?![A-Za-z0-9])")
_URI_CREDENTIAL_REGEX = re.compile(r"(?i)(://[^:\s]+:)([^@\s]+)(@)")
_CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_INDIAN_PAN_REGEX = re.compile(r"(?<![A-Za-z0-9])[A-Z]{5}[0-9]{4}[A-Z](?![A-Za-z0-9])")
_US_SSN_REGEX = re.compile(r"(?<![A-Za-z0-9])\d{3}-\d{2}-\d{4}(?![A-Za-z0-9])")
_SENSITIVE_KEY_REGEX = re.compile(
    r"(?i)(password|secret|token|credential|api_key|apikey|access_token|auth|authorization|client_secret|private_key|pin|pan|ssn|account_number|card_number|iban|cvv|jwt|passwd|pwd)"
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

    text_lower = text.lower()
    sanitized = text

    if "bearer" in text_lower:
        sanitized = _BEARER_TOKEN_REGEX.sub("Bearer [REDACTED_TOKEN]", sanitized)

    if any(
        k in text_lower
        for k in (
            "api_key",
            "apikey",
            "token",
            "access_token",
            "secret",
            "password",
            "passwd",
            "pwd",
            "credential",
        )
    ):
        sanitized = _GENERIC_SECRET_ASSIGN_REGEX.sub(r"\1=[REDACTED]", sanitized)

    if "eyj" in text_lower:
        sanitized = _JWT_TOKEN_REGEX.sub("[REDACTED_JWT]", sanitized)

    if "sk_" in sanitized or "pk_" in sanitized:
        sanitized = _API_KEY_REGEX.sub("[REDACTED_API_KEY]", sanitized)

    if "gh" in sanitized:
        sanitized = _GITHUB_TOKEN_REGEX.sub("[REDACTED_TOKEN]", sanitized)

    if "://" in sanitized and "@" in sanitized:
        sanitized = _URI_CREDENTIAL_REGEX.sub(r"\g<1>[REDACTED]\g<3>", sanitized)

    if any(c.isdigit() for c in sanitized):
        if any(c.isupper() for c in sanitized) and len(sanitized) >= 10:
            sanitized = _INDIAN_PAN_REGEX.sub("[REDACTED_PAN]", sanitized)
        if "-" in sanitized and len(sanitized) >= 11:
            sanitized = _US_SSN_REGEX.sub("[REDACTED_SSN]", sanitized)
        if len(sanitized) >= 13:
            sanitized = _CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", sanitized)

    return sanitized


def redact_dict(
    data: Mapping[str, object],
    depth: int = 0,
    max_depth: int = 8,
    policies: Mapping[str, RedactionPolicy] | None = None,
    default_policy: RedactionPolicy = RedactionPolicy.REDACT,
) -> dict[str, JsonValue]:
    """Recursively scrub sensitive keys and patterns from a dictionary structure.

    Parameters
    ----------
    data : Mapping[str, object]
        Dictionary to sanitize.
    depth : int, default=0
        Current recursion depth.
    max_depth : int, default=8
        Recursion limit to prevent cyclic explosion.
    policies : Mapping[str, RedactionPolicy] | None, default=None
        Field-level redaction policy mappings (SAFE, HASH, REDACT, OMIT).
    default_policy : RedactionPolicy, default=RedactionPolicy.REDACT
        Default policy applied to sensitive keys when not explicitly mapped.

    Returns
    -------
    dict[str, JsonValue]
        Sanitized dictionary with masked sensitive fields.
    """
    if depth > max_depth:
        return {"_truncated": "max_recursion_depth"}

    redacted: dict[str, JsonValue] = {}
    for raw_key, val in data.items():
        key = str(raw_key)
        key_lower = key.lower()

        policy: RedactionPolicy
        if policies is not None and (key in policies or key_lower in policies):
            policy = policies.get(key) or policies[key_lower]
        elif key_lower in SENSITIVE_KEY_SUBSTRINGS or _SENSITIVE_KEY_REGEX.search(key):
            policy = default_policy
        else:
            policy = RedactionPolicy.SAFE

        match policy:
            case RedactionPolicy.OMIT:
                continue
            case RedactionPolicy.HASH:
                redacted[key] = hash_identifier(str(val) if val is not None else "")
            case RedactionPolicy.REDACT:
                redacted[key] = "[REDACTED]"
            case RedactionPolicy.SAFE:
                if isinstance(val, Mapping):
                    mapped_val = cast(Mapping[str, JsonValue], val)
                    redacted[key] = redact_dict(
                        mapped_val,
                        depth=depth + 1,
                        max_depth=max_depth,
                        policies=policies,
                        default_policy=default_policy,
                    )
                elif isinstance(val, (list, tuple, set, frozenset)):
                    redacted_items: list[JsonValue] = []
                    seq_items = cast(Sequence[object], val)
                    for item in seq_items:
                        if isinstance(item, Mapping):
                            mapped_item = cast(Mapping[str, JsonValue], item)
                            redacted_items.append(
                                redact_dict(
                                    mapped_item,
                                    depth=depth + 1,
                                    max_depth=max_depth,
                                    policies=policies,
                                    default_policy=default_policy,
                                )
                            )
                        elif isinstance(item, (int, float, bool)) or item is None:
                            redacted_items.append(item)
                        else:
                            redacted_items.append(redact_text(str(item)))
                    redacted[key] = redacted_items
                elif isinstance(val, (int, float, bool)) or val is None:
                    redacted[key] = val
                else:
                    redacted[key] = redact_text(str(val))

    return redacted


def fingerprint_config(settings: Settings | Mapping[str, object]) -> ConfigFingerprintDict:
    """Generate a deterministic configuration fingerprint and privacy-safe metadata summary.

    Parameters
    ----------
    settings : Settings | Mapping[str, object]
        Application settings instance or settings dictionary.

    Returns
    -------
    ConfigFingerprintDict
        Dictionary containing config SHA-256 fingerprint and safe non-sensitive parameters.
    """
    if isinstance(settings, Settings):
        raw_dict = settings.model_dump(mode="python")
    else:
        raw_dict = dict(settings)

    # Compute deterministic hash over sorted canonical JSON
    canonical_json = json.dumps(raw_dict, sort_keys=True, separators=(",", ":"), default=str)
    config_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    safe_summary: ConfigFingerprintDict = {
        "config_hash": f"sha256_{config_hash[:16]}",
        "target_db_name": str(raw_dict.get("TARGET_DB_NAME", "")),
        "disable_file_discoverer": bool(raw_dict.get("DISABLE_FILE_DISCOVERER", False)),
        "retain_last_n_runs": int(cast(int, raw_dict.get("RETAIN_LAST_N_RUNS", 12))),
        "logs_directory": str(raw_dict.get("LOGS_DIRECTORY", "logs/runs")),
    }
    return safe_summary


def fingerprint_rules(
    rules: FinancialRules | Mapping[str, object] | None,
) -> RulesFingerprintDict:
    """Generate a deterministic financial rules fingerprint and privacy-safe metadata summary.

    Parameters
    ----------
    rules : FinancialRules | Mapping[str, object] | None
        Application financial rules instance or rules mapping, or None if unconfigured.

    Returns
    -------
    RulesFingerprintDict
        Dictionary containing rules SHA-256 fingerprint and safe non-sensitive parameters.
    """
    if rules is None:
        return {
            "rules_hash": "none",
            "default_currency_id": "",
            "investment_instrument_count": 0,
            "has_tax_assumptions": False,
        }

    raw_dict: dict[str, object]
    if isinstance(rules, FinancialRules):
        raw_dict = rules.model_dump(mode="python")
    else:
        raw_dict = dict(rules)

    canonical_json = json.dumps(raw_dict, sort_keys=True, separators=(",", ":"), default=str)
    rules_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    investments = raw_dict.get("investments")
    inst_count = len(cast(Sized, investments)) if isinstance(investments, (dict, list)) else 0
    assumptions = raw_dict.get("assumptions")
    has_tax = isinstance(assumptions, dict) and "tax" in assumptions

    safe_summary: RulesFingerprintDict = {
        "rules_hash": f"sha256_{rules_hash[:16]}",
        "default_currency_id": str(raw_dict.get("DEFAULT_CURRENCY_ID", "INR_INR")),
        "investment_instrument_count": inst_count,
        "has_tax_assumptions": has_tax,
    }
    return safe_summary
