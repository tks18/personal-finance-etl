"""Tax reconciliation and presentation marts subpackage.

Owns
----
- TaxGoldFormatter, TaxReconciler: Formats evidence-based Gold tax analytical views:
  - df_p_tax_year_summary
  - df_p_tax_income_breakdown
  - df_p_tax_reconciliation
- Evidence audit reconciliation between ledger income and Quant realized events.

Does not own
-------------
- Tax event normalization and schema validation (owned by domain.tax.events).
- Storage and warehouse table registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.domain.tax.reconciliation.reconciler import (
    TaxGoldFormatter,
    TaxReconciler,
)
from personal_finance_etl.domain.tax.reconciliation.schemas import (
    RECON_NUMERIC_ZERO_DEFAULTS,
    TAX_INCOME_BREAKDOWN_SCHEMA,
    TAX_RECONCILIATION_SCHEMA,
    TAX_YEAR_SUMMARY_SCHEMA,
    build_fy_agg_expressions,
    build_fy_completeness_columns,
    build_income_breakdown_agg,
    build_income_breakdown_columns,
    build_recon_agg_expressions,
)

__all__ = [
    "RECON_NUMERIC_ZERO_DEFAULTS",
    "TAX_INCOME_BREAKDOWN_SCHEMA",
    "TAX_RECONCILIATION_SCHEMA",
    "TAX_YEAR_SUMMARY_SCHEMA",
    "TaxGoldFormatter",
    "TaxReconciler",
    "build_fy_agg_expressions",
    "build_fy_completeness_columns",
    "build_income_breakdown_agg",
    "build_income_breakdown_columns",
    "build_recon_agg_expressions",
]
