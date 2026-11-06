"""Admission service coordinating Pre-Bronze dataset normalization and row identity resolution.

Owns
----
- AdmissionPlan: Immutable recipe combining NormalizationPlan and IdentityPlan for a dataset.
- AdmissionService: Non-I/O coordination service compiling and executing admission plans.

Does not own
------------
- Mapping or normalization rule execution details (owned by application.normalization).
- Identity derivation or hashing mechanics (owned by application.ingestion.identity and domain.common.identity).
- Physical file reading or database extraction (owned by infrastructure.providers).
- Bronze warehouse storage or persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

from personal_finance_etl.application.ingestion.identity import (
    IdentityPlan,
    compile_identity_plan,
    execute_identity_plan,
)
from personal_finance_etl.application.normalization.compiler import NormalizationCompiler
from personal_finance_etl.application.normalization.executor import NormalizationExecutor
from personal_finance_etl.application.normalization.models import NormalizationPlan
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.infrastructure.warehouse.contracts import BronzeDataContract

__all__ = ["AdmissionPlan", "AdmissionService"]


@dataclass(frozen=True, slots=True)
class AdmissionPlan:
    """Deterministic, immutable execution plan governing dataset normalization and identity.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier being admitted into the Bronze lakehouse.
    source_id : SourceId | None
        Physical source supplying the raw evidence, if bound.
    normalization_plan : NormalizationPlan
        Compiled deterministic column mapping and rule execution plan.
    identity_plan : IdentityPlan
        Compiled deterministic Bronze row identity execution plan.
    id_column : str, default "UID"
        Canonical column name assigned to row identities.
    """

    dataset_id: DatasetId
    source_id: SourceId | None
    normalization_plan: NormalizationPlan
    identity_plan: IdentityPlan
    id_column: str = "UID"


class AdmissionService:
    """Non-I/O coordination service managing admission compilation and execution."""

    def __init__(
        self,
        compiler: NormalizationCompiler | None = None,
        executor: NormalizationExecutor | None = None,
    ) -> None:
        self._compiler = compiler or NormalizationCompiler()
        self._executor = executor or NormalizationExecutor()

    def compile_admission_plan(
        self,
        dataset_config: SourceDatasetConfig,
        bronze_contract: BronzeDataContract,
        available_source_columns: Sequence[str] | None = None,
        *,
        id_column: str = "UID",
        allow_optional_identity: bool = True,
    ) -> AdmissionPlan:
        """Compile a complete immutable admission plan from source config and Bronze contract.

        Parameters
        ----------
        dataset_config : SourceDatasetConfig
            Declarative dataset binding containing mappings, normalization, and identity strategy.
        bronze_contract : BronzeDataContract
            Authoritative warehouse Bronze data contract specifying identity requirements and grain.
        available_source_columns : Sequence[str] | None, optional
            Optional sequence of columns present in the raw incoming source schema.
        id_column : str, default "UID"
            Target column name to receive the canonical row identity.
        allow_optional_identity : bool, default True
            Whether to permit identity strategies on datasets with IdentityRequirement.NONE.

        Returns
        -------
        AdmissionPlan
            Deterministic, validated immutable admission plan ready for execution.
        """
        source_cols = (
            list(available_source_columns) if available_source_columns is not None else None
        )
        norm_plan = self._compiler.compile(dataset_config, available_source_columns=source_cols)

        if norm_plan.expected_output_fields:
            available_for_identity: set[str] = set(norm_plan.expected_output_fields)
        elif available_source_columns is not None:
            available_for_identity = set(available_source_columns)
        else:
            available_for_identity = set()

        ident_plan = compile_identity_plan(
            contract=bronze_contract,
            available_fields=available_for_identity,
            strategy=dataset_config.identity,
            allow_optional_identity=allow_optional_identity,
        )

        return AdmissionPlan(
            dataset_id=dataset_config.dataset_id,
            source_id=dataset_config.source_id,
            normalization_plan=norm_plan,
            identity_plan=ident_plan,
            id_column=id_column,
        )

    def execute_admission(
        self,
        plan: AdmissionPlan,
        frame: pl.LazyFrame | pl.DataFrame,
    ) -> pl.LazyFrame:
        """Execute normalization followed by row identity derivation over an incoming frame.

        Parameters
        ----------
        plan : AdmissionPlan
            Compiled deterministic admission plan.
        frame : pl.LazyFrame | pl.DataFrame
            Source-shaped incoming tabular data frame.

        Returns
        -------
        pl.LazyFrame
            Normalized, canonical LazyFrame with evaluated row identities.
        """
        norm_lf = self._executor.execute(plan.normalization_plan, frame)

        if plan.identity_plan.strategy is not None:
            df = norm_lf.collect()
            result = execute_identity_plan(
                plan.identity_plan,
                df,
                id_column=plan.id_column,
            )
            assert isinstance(result, pl.DataFrame)
            return result.lazy()

        return norm_lf
