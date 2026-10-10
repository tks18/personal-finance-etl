import hashlib
import json
import math
from typing import Any

import numpy as np


def generate_contract_registry_fingerprint(tables_metadata: list[dict[str, Any]]) -> str:
    """
    Computes a deterministic fingerprint of the active table grains and publishers.
    Avoids using a manual registry version counter by hashing the actual structural metadata.
    """
    sorted_metadata = sorted(tables_metadata, key=lambda x: str(x.get("table_name", "")))
    payload = json.dumps(sorted_metadata, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_reproducibility_envelope(
    input_fingerprint: str,
    rules_hash: str,
    macro_settings_hash: str,
    registry_fingerprint: str,
    root_seed: str,
    model_version: str,
) -> dict[str, str]:
    """
    Ties the inputs, rules, macro settings, registry, and seed into the final unified envelope.
    This guarantees that if the envelope hash matches, the simulation is mathematically guaranteed
    to reproduce the exact same Monte Carlo distributions and projections.
    """
    envelope_data = {
        "input_fingerprint": input_fingerprint,
        "rules_hash": rules_hash,
        "macro_settings_hash": macro_settings_hash,
        "registry_fingerprint": registry_fingerprint,
        "root_seed": root_seed,
        "model_version": model_version,
    }
    envelope_payload = json.dumps(envelope_data, sort_keys=True).encode("utf-8")
    envelope_hash = hashlib.sha256(envelope_payload).hexdigest()

    return {
        "envelope_hash": envelope_hash,
        **envelope_data,
    }


def get_standard_prng(seed_string: str) -> Any:
    """
    Returns a standardized high-grade Pseudo-Random Number Generator (PRNG)
    for financial Monte Carlo simulations. Uses NumPy's PCG64 (Permuted Congruential Generator).
    The string seed is hashed into a deterministically derived integer seed.
    """
    # Deterministically convert the string seed into an integer suitable for PCG64
    seed_int = int(hashlib.sha256(seed_string.encode('utf-8')).hexdigest()[:15], 16)
    
    # PCG64 is statistically excellent and highly performant for Monte Carlo simulations
    return np.random.Generator(np.random.PCG64(seed_int))


def assert_simulation_replay(actual_val: float, expected_val: float, context: str = "") -> None:
    """
    Enforces the Simulation Replay Numerical Contract.
    Standardizes strict numerical tolerances for asserting simulation equivalence 
    across rebuilds or version upgrades.
    """
    # rel_tol of 1e-5 (0.001%) and abs_tol of 1e-4
    if not math.isclose(actual_val, expected_val, rel_tol=1e-5, abs_tol=1e-4):
        raise ValueError(
            f"Simulation replay contract broken {context}: "
            f"expected {expected_val}, got {actual_val}."
        )

