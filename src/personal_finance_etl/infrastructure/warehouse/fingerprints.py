"""Deterministic cryptographic fingerprinting for warehouse contracts and registries.

Owns
----
- SHA-256 fingerprint generation for active warehouse schema metadata and contracts.
- Deterministic serialization of structural table grains and publishers.

Does not own
-------------
- Simulation reproducibility envelopes or PRNG state (owned by domain.fire.reproducibility).
- Physical warehouse publication contracts (owned by infrastructure.warehouse.registry).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence


def generate_contract_registry_fingerprint(
    tables_metadata: Sequence[Mapping[str, object]],
) -> str:
    """Compute a deterministic SHA-256 fingerprint of active table grains and publishers.

    Avoids using a manual registry version counter by hashing the actual structural metadata.

    Parameters
    ----------
    tables_metadata : Sequence[Mapping[str, object]]
        Sequence of dictionaries containing table metadata attributes.

    Returns
    -------
    str
        Hexadecimal SHA-256 digest string.
    """
    sorted_metadata = sorted(tables_metadata, key=lambda x: str(x.get("table_name", "")))
    payload = json.dumps(sorted_metadata, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
