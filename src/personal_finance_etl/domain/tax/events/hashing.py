"""Deterministic Tax Event identity calculation routines.

Owns
----
- _batch_compute_tax_event_ids: Batch calculation of deterministic Tax_Event_IDs.

Does not own
-------------
- Underlying SHA256 deterministic ID generator (owned by domain.common.identity).
- TaxEvent schema definition (owned by domain.tax.events.builder.schema).
- TaxEvent evidence normalizer (owned by domain.tax.events.builder).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.domain.common.identity import generate_deterministic_id

__all__ = ["_batch_compute_tax_event_ids"]


def _batch_compute_tax_event_ids(s: pl.Series) -> pl.Series:
    """Compute deterministic Tax_Event_IDs in batches using Polars struct map."""
    source_types = s.struct.field("Source_Type")
    source_ids = s.struct.field("Source_ID")
    sub_heads = s.struct.field("Tax_Sub_Head")
    ids = [
        generate_deterministic_id(
            "TAX",
            {
                "Source_Type": st,
                "Source_ID": sid,
                "Tax_Sub_Head": tsh,
            },
        )
        for st, sid, tsh in zip(source_types, source_ids, sub_heads, strict=False)
    ]
    return pl.Series(ids, dtype=pl.String)
