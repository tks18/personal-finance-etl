"""Declarative canonical household route definitions and production declarations.

Owns
----
- CANONICAL_HOUSEHOLD_ROUTE_ID: Authoritative route identifier for canonical household projections.
- HOUSEHOLD_CANONICAL_TARGET_MAP: Mapping from legacy household DatasetId to canonical DatasetId.
- build_household_canonical_route: Factory constructing CanonicalRouteConfig for a given household binding.
- build_household_canonical_production: Factory constructing CanonicalDatasetProductionConfig.
- is_household_transitional_dataset: Inspection predicate identifying legacy household datasets.

Does not own
------------
- Route compilation or execution (owned by application.ingestion).
- Schema validation (owned by infrastructure.validation).
- Medallion persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    CanonicalRouteConfig,
)
from personal_finance_etl.config.sources.identity import SourceFieldIdentity
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.normalization import (
    CastRule,
    NormalizeNullRule,
)
from personal_finance_etl.config.sources.semantics import (
    ExcludeWhen,
    PredicateOperator,
    SemanticMapRule,
)
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.canonical_semantics import (
    HouseholdCategoryKind,
    HouseholdTransactionKind,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    SourceBindingId,
)

__all__ = [
    "CANONICAL_HOUSEHOLD_ROUTE_ID",
    "HOUSEHOLD_CANONICAL_TARGET_MAP",
    "build_household_canonical_production",
    "build_household_canonical_route",
    "is_household_transitional_dataset",
]

CANONICAL_HOUSEHOLD_ROUTE_ID: CanonicalRouteId = CanonicalRouteId("canonical")

HOUSEHOLD_CANONICAL_TARGET_MAP: dict[DatasetId, DatasetId] = {
    DatasetId.HOUSEHOLD_ZCATEGORY: DatasetId.HOUSEHOLD_CATEGORIES,
    DatasetId.HOUSEHOLD_ASSET_GROUP: DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
    DatasetId.HOUSEHOLD_ASSETS: DatasetId.HOUSEHOLD_ACCOUNTS,
    DatasetId.HOUSEHOLD_CURRENCY: DatasetId.COMMON_CURRENCIES,
    DatasetId.HOUSEHOLD_INOUTCOME: DatasetId.HOUSEHOLD_TRANSACTIONS,
    DatasetId.HOUSEHOLD_OPENING_BALANCES: DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
}


def is_household_transitional_dataset(dataset_id: DatasetId) -> bool:
    """Check whether a dataset is a legacy household dataset with a canonical counterpart.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical or legacy dataset identifier.

    Returns
    -------
    bool
        True if the dataset is an old household dataset being migrated in Phase 052.
    """
    return dataset_id in HOUSEHOLD_CANONICAL_TARGET_MAP


def build_household_canonical_route(
    legacy_dataset_id: DatasetId,
) -> CanonicalRouteConfig | None:
    """Construct the declarative canonical route for a legacy household binding.

    Parameters
    ----------
    legacy_dataset_id : DatasetId
        Legacy household dataset identifier.

    Returns
    -------
    CanonicalRouteConfig | None
        Constructed canonical route configuration, or None if not a household dataset.
    """
    if legacy_dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY:
        return CanonicalRouteConfig(
            route_id=CANONICAL_HOUSEHOLD_ROUTE_ID,
            target_dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
            description="Canonical household category hierarchy and semantic kind projection",
            enabled=True,
            predicates=[
                ExcludeWhen(field="C_IS_DEL", operator=PredicateOperator.EQUALS, value=1),
            ],
            mapping=[
                ColumnMapping(source_field="uid", canonical_field="category_id"),
                ColumnMapping(source_field="NAME", canonical_field="category_name"),
                ColumnMapping(source_field="pUid", canonical_field="parent_category_id"),
                ColumnMapping(source_field="TYPE", canonical_field="category_kind"),
            ],
            semantics=[
                SemanticMapRule(
                    field="category_kind",
                    mapping={
                        "0": HouseholdCategoryKind.INCOME.value,
                        "1": HouseholdCategoryKind.EXPENSE.value,
                    },
                    on_unmapped="error",
                ),
            ],
            normalization=[
                NormalizeNullRule(field="parent_category_id", null_values=["", " ", "0"]),
            ],
            identity=SourceFieldIdentity(field="category_id"),
        )

    if legacy_dataset_id == DatasetId.HOUSEHOLD_ASSET_GROUP:
        return CanonicalRouteConfig(
            route_id=CANONICAL_HOUSEHOLD_ROUTE_ID,
            target_dataset_id=DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
            description="Canonical household asset category projection",
            enabled=True,
            predicates=[
                ExcludeWhen(field="IS_DEL", operator=PredicateOperator.EQUALS, value=1),
            ],
            mapping=[
                ColumnMapping(source_field="uid", canonical_field="asset_category_id"),
                ColumnMapping(source_field="ACC_GROUP_NAME", canonical_field="asset_category_name"),
            ],
            identity=SourceFieldIdentity(field="asset_category_id"),
        )

    if legacy_dataset_id == DatasetId.HOUSEHOLD_ASSETS:
        return CanonicalRouteConfig(
            route_id=CANONICAL_HOUSEHOLD_ROUTE_ID,
            target_dataset_id=DatasetId.HOUSEHOLD_ACCOUNTS,
            description="Canonical household accounts and asset master projection",
            enabled=True,
            predicates=[
                ExcludeWhen(field="ZDATA", operator=PredicateOperator.NOT_EQUALS, value="0"),
            ],
            mapping=[
                ColumnMapping(source_field="uid", canonical_field="asset_id"),
                ColumnMapping(source_field="NIC_NAME", canonical_field="asset_name"),
                ColumnMapping(source_field="groupUid", canonical_field="asset_category_id"),
                ColumnMapping(source_field="currencyUid", canonical_field="currency_id"),
                ColumnMapping(source_field="ZDATA1", canonical_field="description"),
                ColumnMapping(source_field="ZDATA2", canonical_field="notes"),
            ],
            normalization=[
                NormalizeNullRule(field="description", null_values=["", " "]),
                NormalizeNullRule(field="notes", null_values=["", " "]),
            ],
            identity=SourceFieldIdentity(field="asset_id"),
        )

    if legacy_dataset_id == DatasetId.HOUSEHOLD_CURRENCY:
        return CanonicalRouteConfig(
            route_id=CANONICAL_HOUSEHOLD_ROUTE_ID,
            target_dataset_id=DatasetId.COMMON_CURRENCIES,
            description="Canonical provider-neutral currency master projection",
            enabled=True,
            predicates=[
                ExcludeWhen(field="IS_DEL", operator=PredicateOperator.EQUALS, value=1),
            ],
            mapping=[
                ColumnMapping(source_field="uid", canonical_field="currency_id"),
                ColumnMapping(source_field="NAME", canonical_field="currency_name"),
                ColumnMapping(source_field="ISO", canonical_field="iso_code"),
                ColumnMapping(source_field="SYMBOL", canonical_field="symbol"),
            ],
            normalization=[
                NormalizeNullRule(field="symbol", null_values=["", " "]),
            ],
            identity=SourceFieldIdentity(field="currency_id"),
        )

    if legacy_dataset_id == DatasetId.HOUSEHOLD_INOUTCOME:
        return CanonicalRouteConfig(
            route_id=CANONICAL_HOUSEHOLD_ROUTE_ID,
            target_dataset_id=DatasetId.HOUSEHOLD_TRANSACTIONS,
            description="Canonical household transaction observations projection",
            enabled=True,
            predicates=[
                ExcludeWhen(field="IS_DEL", operator=PredicateOperator.EQUALS, value=1),
                ExcludeWhen(field="DO_TYPE", operator=PredicateOperator.EQUALS, value="7"),
            ],
            mapping=[
                ColumnMapping(source_field="uid", canonical_field="transaction_id"),
                ColumnMapping(source_field="WDATE", canonical_field="transaction_date"),
                ColumnMapping(source_field="wtime", canonical_field="transaction_time"),
                ColumnMapping(source_field="assetUid", canonical_field="asset_id"),
                ColumnMapping(source_field="toAssetUid", canonical_field="to_asset_id"),
                ColumnMapping(source_field="ctgUid", canonical_field="category_id"),
                ColumnMapping(source_field="currencyUid", canonical_field="currency_id"),
                ColumnMapping(source_field="ZMONEY", canonical_field="base_amount"),
                ColumnMapping(source_field="IN_ZMONEY", canonical_field="local_amount"),
                ColumnMapping(source_field="AMOUNT_ACCOUNT", canonical_field="account_amount"),
                ColumnMapping(source_field="ZCONTENT", canonical_field="description"),
                ColumnMapping(source_field="txUidTrans", canonical_field="transfer_id"),
                ColumnMapping(source_field="DO_TYPE", canonical_field="transaction_kind"),
            ],
            semantics=[
                SemanticMapRule(
                    field="transaction_kind",
                    mapping={
                        "0": HouseholdTransactionKind.INCOME.value,
                        "1": HouseholdTransactionKind.EXPENSE.value,
                        "2": HouseholdTransactionKind.TRANSFER.value,
                        "3": HouseholdTransactionKind.TRANSFER_OUT.value,
                        "4": HouseholdTransactionKind.TRANSFER_IN.value,
                    },
                    on_unmapped="error",
                ),
            ],
            normalization=[
                NormalizeNullRule(field="to_asset_id", null_values=["", " "]),
                NormalizeNullRule(field="category_id", null_values=["", " "]),
                NormalizeNullRule(field="transfer_id", null_values=["", " "]),
                NormalizeNullRule(field="description", null_values=["", " "]),
                NormalizeNullRule(field="transaction_time", null_values=["", " "]),
                CastRule(field="transaction_time", target_type="string"),
                CastRule(field="to_asset_id", target_type="string"),
                CastRule(field="category_id", target_type="string"),
                CastRule(field="transfer_id", target_type="string"),
                CastRule(field="description", target_type="string"),
                CastRule(field="base_amount", target_type="float64"),
                CastRule(field="local_amount", target_type="float64"),
                CastRule(field="account_amount", target_type="float64"),
            ],
            identity=SourceFieldIdentity(field="transaction_id"),
        )

    if legacy_dataset_id == DatasetId.HOUSEHOLD_OPENING_BALANCES:
        return CanonicalRouteConfig(
            route_id=CANONICAL_HOUSEHOLD_ROUTE_ID,
            target_dataset_id=DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
            description="Canonical household opening account balances observation projection",
            enabled=True,
            mapping=[
                ColumnMapping(source_field="ZTXDATESTR", canonical_field="balance_date"),
                ColumnMapping(source_field="ZASSETUID", canonical_field="asset_id"),
                ColumnMapping(source_field="ZCURRENCYUID", canonical_field="currency_id"),
                ColumnMapping(source_field="ZAMOUNT", canonical_field="opening_amount"),
                ColumnMapping(
                    source_field="ZAMOUNTACCOUNT", canonical_field="opening_amount_account"
                ),
                ColumnMapping(source_field="Z_PK", canonical_field="opening_balance_id"),
            ],
            normalization=[
                CastRule(field="opening_amount", target_type="float64"),
                CastRule(field="opening_amount_account", target_type="float64"),
                CastRule(field="opening_balance_id", target_type="string"),
            ],
            identity=SourceFieldIdentity(field="opening_balance_id"),
        )

    return None


def build_household_canonical_production(
    binding_id: SourceBindingId,
    legacy_dataset_id: DatasetId,
) -> CanonicalDatasetProductionConfig | None:
    """Construct the CanonicalDatasetProductionConfig for a canonical household target.

    Parameters
    ----------
    binding_id : SourceBindingId
        Parent physical source binding identity.
    legacy_dataset_id : DatasetId
        Legacy household dataset identifier.

    Returns
    -------
    CanonicalDatasetProductionConfig | None
        Production declaration for the canonical dataset, or None if not household.
    """
    target_ds = HOUSEHOLD_CANONICAL_TARGET_MAP.get(legacy_dataset_id)
    if target_ds is None:
        return None

    return CanonicalDatasetProductionConfig(
        dataset_id=target_ds,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        source_routes=[
            CanonicalRouteRef(
                binding_id=binding_id,
                route_id=CANONICAL_HOUSEHOLD_ROUTE_ID,
            )
        ],
        enabled=True,
        description=f"Phase 052 direct canonical production for {target_ds.value}",
    )
