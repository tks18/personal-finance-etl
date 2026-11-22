"""Filesystem evidence discovery driven purely by compiled SourcePlans.

Owns
----
- Scanning physical source locations for evidence artifacts based on DatasetPlan selectors.
- Resolving exact files, folder directories with file_pattern or provider extension, and recursive globs.
- Filtering transient lock or temporary files (e.g. starting with ~ or .).
- Returning deterministic, normalized, POSIX-separated paths keyed by dataset_id.value.

Does not own
-------------
- Control plane artifact vaulting or hashing (owned by control plane).
- Pre-Bronze persistence or validation (owned by PreBronzeLayer and Pandera).
- Schema validation or semantic interpretation (owned by domain and contracts).
"""

from __future__ import annotations

import glob
import os
from collections.abc import Iterable, Sequence

from personal_finance_etl.application.pipeline.source_planner import SourcePlan
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
)
from personal_finance_etl.contracts.sources import ProviderType
from personal_finance_etl.infrastructure.control_plane.hashing import normalize_path
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.providers.files.sqlite import SQLiteExtractor

__all__ = ["discover_source_plan_files"]

diagnostics = get_observability_diagnostics(__name__)


def _match_source_files(
    norm_location: str, provider_type: ProviderType, selector: object
) -> list[str]:
    """Match physical files for a given provider type, selector, and location."""
    if provider_type == ProviderType.SQLITE:
        if os.path.isfile(norm_location):
            return [norm_location]
        if os.path.isdir(norm_location):
            extractor = SQLiteExtractor(norm_location)
            latest_backup = extractor.get_latest_sqlite_backup()
            if latest_backup:
                return [normalize_path(latest_backup)]
        return []

    if provider_type in (ProviderType.CSV, ProviderType.EXCEL):
        pattern: str | None = None
        if isinstance(selector, (CsvSelector, ExcelSelector)):
            pattern = selector.file_pattern

        if os.path.isfile(norm_location):
            return [norm_location]
        if os.path.isdir(norm_location):
            if pattern:
                if "**" not in pattern and not os.path.isabs(pattern):
                    search_pattern = os.path.join(norm_location, "**", pattern)
                else:
                    search_pattern = os.path.join(norm_location, pattern)
                raw_matches = glob.glob(search_pattern, recursive=True)
            else:
                ext_pattern = "*.csv" if provider_type == ProviderType.CSV else "*.[xX][lL][sS]*"
                search_pattern = os.path.join(norm_location, "**", ext_pattern)
                raw_matches = glob.glob(search_pattern, recursive=True)
            return [
                normalize_path(p)
                for p in raw_matches
                if not os.path.basename(p).startswith(("~", "."))
            ]

        raw_matches = glob.glob(norm_location, recursive=True)
        return [
            normalize_path(p) for p in raw_matches if not os.path.basename(p).startswith(("~", "."))
        ]

    return []


def discover_source_plan_files(
    source_plans: Sequence[SourcePlan] | Iterable[SourcePlan],
) -> dict[str, list[str]]:
    """Discover filesystem evidence artifacts driven purely by compiled SourcePlans.

    Parameters
    ----------
    source_plans : Sequence[SourcePlan] | Iterable[SourcePlan]
        Authoritative source plans compiled from SourceConfiguration and ExecutionPlan.

    Returns
    -------
    dict[str, list[str]]
        Dictionary mapping SourceBindingId and canonical dataset_id values to sorted, unique normalized filepaths.
    """
    discovered: dict[str, list[str]] = {}

    for sp in source_plans:
        if not sp.enabled:
            continue

        # Skip provider-generated streams (managed via external HTTP fetchers, not disk)
        if sp.provider_type == ProviderType.MARKET_DATA:
            continue

        location = sp.location.strip()
        if not location:
            continue

        norm_location = normalize_path(location)

        # Prefer binding_plans for physical evidence discovery
        if sp.binding_plans:
            for bp in sp.binding_plans:
                if not bp.enabled:
                    continue

                matched_files = sorted(
                    set(_match_source_files(norm_location, bp.provider_type, bp.selector))
                )
                if matched_files:
                    b_key = str(bp.binding_id)
                    discovered.setdefault(b_key, []).extend(matched_files)
                    discovered[b_key] = sorted(set(discovered[b_key]))

                    # Attach transitional dataset_id keys for compatibility
                    for dp in sp.dataset_plans:
                        if dp.dataset_id.value in b_key or dp.selector == bp.selector:
                            ds_key = dp.dataset_id.value
                            discovered.setdefault(ds_key, []).extend(matched_files)
                            discovered[ds_key] = sorted(set(discovered[ds_key]))
        else:
            # Fallback for source plans with only dataset_plans
            for dp in sp.dataset_plans:
                if not dp.is_enabled:
                    continue

                ds_key = dp.dataset_id.value
                matched_files = sorted(
                    set(_match_source_files(norm_location, dp.provider_type, dp.selector))
                )
                if matched_files:
                    discovered.setdefault(ds_key, []).extend(matched_files)
                    discovered[ds_key] = sorted(set(discovered[ds_key]))

    return discovered
