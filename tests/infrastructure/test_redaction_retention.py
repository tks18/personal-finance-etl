"""Observability Privacy, Redaction, and Retention Certification Test Suite.

Owns
----
- Verification of pattern-based text redaction (Bearer tokens, cards, PAN, SSN, passwords).
- Verification of recursive dictionary redaction across arbitrary telemetry payloads.
- Verification of deterministic anonymous entity hashing.
- Verification of privacy-safe configuration fingerprinting.
- Verification of JSONL sink automatic redaction at disk write boundary.
- Verification of trace file retention pruning (run count and age-based bounds).

Does not own
-------------
- Control Plane database record purging (owned by infrastructure.control_plane).
- Presentation narrative rendering (owned by presentation).
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    EventOutcome,
    FailureDomain,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability.forensic_sink import JsonlForensicSink
from personal_finance_etl.infrastructure.observability.redaction import (
    RedactionPolicy,
    fingerprint_config,
    hash_identifier,
    redact_dict,
    redact_text,
)
from personal_finance_etl.infrastructure.observability.retention import LogRetentionManager


def test_redact_text_masks_sensitive_patterns() -> None:
    """Verify regex masks Bearer tokens, credit cards, Indian PANs, and SSNs."""
    # Bearer token
    raw_token = "Authorization header: Bearer ya29.a0AfH6SMBxyz1234567890abcdef"
    clean_token = redact_text(raw_token)
    assert "ya29" not in clean_token
    assert clean_token == "Authorization header: Bearer [REDACTED_TOKEN]"

    # Indian PAN
    raw_pan = "Customer tax account PAN is ABCDE1234F verified."
    clean_pan = redact_text(raw_pan)
    assert "ABCDE1234F" not in clean_pan
    assert clean_pan == "Customer tax account PAN is [REDACTED_PAN] verified."

    # US SSN
    raw_ssn = "Customer SSN identifier 987-65-4321 on file."
    clean_ssn = redact_text(raw_ssn)
    assert "987-65-4321" not in clean_ssn
    assert clean_ssn == "Customer SSN identifier [REDACTED_SSN] on file."

    # Credit card number
    raw_card = "Processed card 4111 2222 3333 4444 successfully."
    clean_card = redact_text(raw_card)
    assert "4111" not in clean_card
    assert clean_card == "Processed card [REDACTED_CARD] successfully."

    # Key-value assignment in string
    raw_assign = "Connecting with api_key='sk_live_abcdef123456'..."
    clean_assign = redact_text(raw_assign)
    assert "sk_live" not in clean_assign
    assert "api_key=[REDACTED]" in clean_assign


def test_hash_identifier_deterministic_and_anonymous() -> None:
    """Verify hash_identifier produces deterministic, truncated hashes with prefixes."""
    h1 = hash_identifier("user@example.com")
    h2 = hash_identifier("user@example.com")
    h3 = hash_identifier("different_user@example.com")

    assert h1 == h2
    assert h1 != h3
    assert h1.startswith("id_")
    assert len(h1) == 13  # 'id_' + 10 chars
    assert "user@example.com" not in h1


def test_redact_dict_scrubs_nested_structures() -> None:
    """Verify recursive dictionary traversal scrubs sensitive keys and values."""
    payload = {
        "user_id": "usr_100",
        "api_key": "secret_xyz12345",
        "account_number": "123456789012",
        "settings": {
            "password": "SuperSecretPassword123!",
            "database": "analytics.duckdb",
            "notes": "Contact user at PAN: ABCDE9999Z for inquiries",
        },
        "log_entries": [
            "Normal log message",
            "Encountered Bearer secret_token_1234567890 in header",
        ],
    }

    sanitized = redact_dict(payload)

    assert sanitized["user_id"] == "usr_100"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["account_number"] == "[REDACTED]"
    settings_dict = cast(dict[str, object], sanitized["settings"])
    assert settings_dict["password"] == "[REDACTED]"
    assert settings_dict["database"] == "analytics.duckdb"
    assert "ABCDE9999Z" not in str(settings_dict["notes"])
    assert "[REDACTED_PAN]" in str(settings_dict["notes"])
    log_entries = cast(list[object], sanitized["log_entries"])
    assert log_entries[0] == "Normal log message"
    assert "secret_token" not in str(log_entries[1])
    assert "[REDACTED_TOKEN]" in str(log_entries[1])


def test_fingerprint_config_produces_safe_summary() -> None:
    """Verify fingerprint_config summarizes configuration without leaking secret paths."""
    cfg = Settings(
        TARGET_DB_BASE_PATH="/path/to/private/vault",
        TARGET_DB_NAME="MyFinances.duckdb",
        RETAIN_LAST_N_RUNS=15,
    )

    summary = fingerprint_config(cfg)

    assert "config_hash" in summary
    assert summary["config_hash"].startswith("sha256_")
    assert summary["target_db_name"] == "MyFinances.duckdb"
    assert summary["retain_last_n_runs"] == 15
    # Absolute user folder path should not be in the summary root
    assert "/path/to/private/vault" not in str(summary.values())


def test_jsonl_forensic_sink_applies_redaction(tmp_path: Path) -> None:
    """Verify JsonlForensicSink automatically scrubs sensitive data on write."""
    log_file = tmp_path / "forensic_trace.jsonl"
    sink = JsonlForensicSink(log_file)

    err = ErrorDetails(
        exception_type="AuthError",
        exception_message="Invalid credentials with api_key='sk_test_123456789'",
        failure_domain=FailureDomain.EXTERNAL_PROVIDER,
        traceback_summary="Traceback: password=Secret12345 failed",
    )
    event = ObservabilityEvent(
        timestamp=datetime.now(UTC),
        event_code=EventCode.RUN_FAILED,
        severity=DiagnosticSeverity.ERROR,
        presentation_kind=PresentationKind.FAILURE,
        outcome=EventOutcome.FAILED,
        context=ObservabilityContext(run_id="run-test-01"),
        message="Request failed: Bearer secret_bearer_token_xyz1234567",
        error=err,
    )

    sink.emit(event)
    sink.flush()
    sink.close()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])

    # Message must be redacted
    assert "secret_bearer_token" not in parsed["message"]
    assert "Bearer [REDACTED_TOKEN]" in parsed["message"]

    # Error payload must be redacted
    assert "sk_test" not in parsed["error"]["exception_message"]
    assert "api_key=[REDACTED]" in parsed["error"]["exception_message"]


def test_retention_manager_run_count_bound(tmp_path: Path) -> None:
    """Verify LogRetentionManager prunes files beyond retain_last_n_runs."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    # Create 15 trace files with distinct modification times
    for i in range(15):
        f = logs_dir / f"run_20261022_{i:02d}.jsonl"
        f.write_text(f'{{"index": {i}}}\n', encoding="utf-8")
        # Set mtime staggered by i seconds
        t = time.time() - (15 - i) * 10
        os.utime(f, (t, t))

    mgr = LogRetentionManager(logs_dir=logs_dir, retain_last_n_runs=10, max_age_days=None)

    # Dry run check
    candidates = mgr.prune_expired_traces(dry_run=True)
    assert len(candidates) == 5
    assert len(mgr.discover_trace_files()) == 15

    # Actual prune
    pruned = mgr.prune_expired_traces(dry_run=False)
    assert len(pruned) == 5

    remaining = mgr.discover_trace_files()
    assert len(remaining) == 10
    # Verify remaining files are the newest ones (indices 5 through 14)
    remaining_names = {p.name for p in remaining}
    assert "run_20261022_14.jsonl" in remaining_names
    assert "run_20261022_00.jsonl" not in remaining_names


def test_retention_manager_age_bound(tmp_path: Path) -> None:
    """Verify LogRetentionManager prunes files older than max_age_days."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    now = time.time()
    # File 1: 5 days old
    f_fresh = logs_dir / "recent.jsonl"
    f_fresh.write_text('{"status": "fresh"}', encoding="utf-8")
    t_fresh = now - 5 * 86400
    os.utime(f_fresh, (t_fresh, t_fresh))

    # File 2: 45 days old (exceeds 30 days)
    f_old = logs_dir / "ancient.jsonl"
    f_old.write_text('{"status": "old"}', encoding="utf-8")
    t_old = now - 45 * 86400
    os.utime(f_old, (t_old, t_old))

    mgr = LogRetentionManager(logs_dir=logs_dir, retain_last_n_runs=10, max_age_days=30)
    pruned = mgr.prune_expired_traces(dry_run=False)

    assert len(pruned) == 1
    assert pruned[0].name == "ancient.jsonl"
    assert f_fresh.exists()
    assert not f_old.exists()


def test_redaction_policy_matrix() -> None:
    """Verify SAFE, HASH, REDACT, and OMIT policies work accurately."""
    payload: dict[str, object] = {
        "safe_param": "regular_value",
        "user_account": "ACC_998877",
        "access_token": "secret_token_12345",
        "pin_code": "9876",
    }
    policies: dict[str, RedactionPolicy] = {
        "safe_param": RedactionPolicy.SAFE,
        "user_account": RedactionPolicy.HASH,
        "access_token": RedactionPolicy.REDACT,
        "pin_code": RedactionPolicy.OMIT,
    }

    sanitized = redact_dict(payload, policies=policies)

    # SAFE: retained as is
    assert sanitized["safe_param"] == "regular_value"
    # HASH: deterministic hashed string
    assert isinstance(sanitized["user_account"], str)
    assert sanitized["user_account"].startswith("id_")
    assert "ACC_998877" not in sanitized["user_account"]
    assert sanitized["user_account"] == hash_identifier("ACC_998877")
    # REDACT: masked with [REDACTED]
    assert sanitized["access_token"] == "[REDACTED]"
    # OMIT: key is completely dropped
    assert "pin_code" not in sanitized


def test_redact_text_adversarial_patterns() -> None:
    """Verify adversarial secrets, tokens, JWTs, and database URIs are sanitized."""
    # JWT token
    jwt_input = "Session bearer: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgN_pGMstVEMmPO_c"
    jwt_clean = redact_text(jwt_input)
    assert "eyJhbGciOi" not in jwt_clean
    assert "[REDACTED_JWT]" in jwt_clean

    # OpenAI / Stripe style API keys
    api_key_input = "Loaded model using sk_live_1234567890abcdef1234567890 securely."
    api_key_clean = redact_text(api_key_input)
    assert "sk_live_" not in api_key_clean
    assert "[REDACTED_API_KEY]" in api_key_clean

    # GitHub token
    gh_input = "Syncing repo via ghp_1234567890abcdef1234567890abcdef1234"
    gh_clean = redact_text(gh_input)
    assert "ghp_" not in gh_clean
    assert "[REDACTED_TOKEN]" in gh_clean

    # Database connection string with password
    uri_input = "Connecting to postgresql://postgres:SuperSecretPassword@localhost:5432/finance_db"
    uri_clean = redact_text(uri_input)
    assert "SuperSecretPassword" not in uri_clean
    assert "Connecting to postgresql://postgres:[REDACTED]@localhost:5432/finance_db" == uri_clean

    # Key assignments
    assign_input = "Config loaded with password='MyVaultPassword123' and credential = 'AdminCredential456'"
    assign_clean = redact_text(assign_input)
    assert "MyVaultPassword123" not in assign_clean
    assert "AdminCredential456" not in assign_clean
    assert "password=[REDACTED]" in assign_clean
    assert "credential=[REDACTED]" in assign_clean


def test_jsonl_forensic_sink_full_payload_scrubbing(tmp_path: Path) -> None:
    """Verify JsonlForensicSink scrubs sensitive identifiers across all payload sub-dictionaries."""
    log_file = tmp_path / "forensic_adversarial.jsonl"
    sink = JsonlForensicSink(log_file)

    err = ErrorDetails(
        exception_type="DatabaseError",
        exception_message="Failed connecting to postgresql://admin:SuperSecretPwd123@prod-db.internal:5432/ledger",
        failure_domain=FailureDomain.SOURCE_VALIDATION,
        traceback_summary="File 'auth.py', line 42, in connect: token='ghp_secrettoken12345678901234567890123456' invalid",
    )
    ctx = ObservabilityContext(
        run_id="run-adv-01",
        stage=EngineStage.EXTRACTING,
        component="db_adapter_sk_test_1234567890abcdef12345678",
        operation="fetch_pan_ABCDE1234F_statement",
        entity_id="987-65-4321",
    )
    event = ObservabilityEvent.create(
        event_code=EventCode.RUN_FAILED,
        message="Request failed: Bearer ya29.a0AfH6SMBxyz1234567890abcdef with sk_live_1234567890abcdef1234567890",
        context=ctx,
        severity=DiagnosticSeverity.ERROR,
        presentation_kind=PresentationKind.FAILURE,
        outcome=EventOutcome.FAILED,
        error=err,
    )

    sink.emit(event)
    sink.flush()
    sink.close()

    raw_content = log_file.read_text(encoding="utf-8")

    # Assert ZERO secrets leaked into raw file
    assert "ya29.a0AfH6SMB" not in raw_content
    assert "sk_live_" not in raw_content
    assert "sk_test_" not in raw_content
    assert "SuperSecretPwd123" not in raw_content
    assert "ABCDE1234F" not in raw_content
    assert "987-65-4321" not in raw_content
    assert "ghp_secrettoken" not in raw_content

    # Assert proper replacement tokens appear
    assert "Bearer [REDACTED_TOKEN]" in raw_content
    assert "[REDACTED_API_KEY]" in raw_content
    assert "[REDACTED_PAN]" in raw_content
    assert "[REDACTED_SSN]" in raw_content
    assert "token=[REDACTED]" in raw_content

    # Verify structured ndjson can still be parsed natively
    parsed = json.loads(raw_content.strip())
    assert parsed["context"]["operation"] == "fetch_pan_[REDACTED_PAN]_statement"
    assert parsed["context"]["entity_id"] == "[REDACTED_SSN]"


def test_jsonl_forensic_sink_with_policy_overrides(tmp_path: Path) -> None:
    """Verify JsonlForensicSink respects custom policy mappings (e.g. HASH entity_id)."""
    log_file = tmp_path / "forensic_policies.jsonl"
    policies: dict[str, RedactionPolicy] = {
        "entity_id": RedactionPolicy.HASH,
    }
    sink = JsonlForensicSink(log_file, policies=policies)

    ctx = ObservabilityContext(
        run_id="run-hash-01",
        entity_id="user_account_998811",
    )
    event = ObservabilityEvent.create(
        event_code=EventCode.DISCOVERY_START,
        message="Discovery phase started",
        context=ctx,
    )

    sink.emit(event)
    sink.flush()
    sink.close()

    raw_content = log_file.read_text(encoding="utf-8")
    assert "user_account_998811" not in raw_content

    parsed = json.loads(raw_content.strip())
    assert parsed["context"]["entity_id"].startswith("id_")
    assert parsed["context"]["entity_id"] == hash_identifier("user_account_998811")

