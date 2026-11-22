"""Authoritative registry for PFETL-owned canonical derivation recipes.

Owns
----
- CanonicalRecipeRegistry: Centralized, typed registry for PFETL-owned canonical derivation recipes.
- Registration, metadata discovery, and deterministic execution of derivation recipes.
- Enforcement against arbitrary user code; only certified, typed internal callables may be registered.

Does not own
-------------
- Physical source extraction (owned by infrastructure.providers).
- Pandera schema validation (owned by infrastructure.validation).
- Capability graph or execution planning (owned by contracts.capabilities and application.pipeline.planner).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import polars as pl

from personal_finance_etl.contracts.canonical_recipes import (
    CanonicalProductionError,
    CanonicalRecipeDescriptor,
    UnresolvedRecipeError,
)
from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "CanonicalRecipeRegistry",
    "RecipeRunner",
]

type RecipeRunner = Callable[[Mapping[DatasetId, pl.DataFrame]], pl.DataFrame]


class CanonicalRecipeRegistry:
    """Authoritative registry managing registered PFETL canonical derivation recipes."""

    def __init__(self) -> None:
        self._descriptors: dict[str, CanonicalRecipeDescriptor] = {}
        self._runners: dict[str, RecipeRunner] = {}

    def register(
        self,
        descriptor: CanonicalRecipeDescriptor,
        runner: RecipeRunner,
    ) -> None:
        """Register a new certified canonical derivation recipe.

        Parameters
        ----------
        descriptor : CanonicalRecipeDescriptor
            Typed metadata describing the derivation recipe.
        runner : RecipeRunner
            Vectorized callable computing the canonical target DataFrame from canonical dependencies.

        Raises
        ------
        ValueError
            If recipe_id is already registered.
        """
        recipe_id = descriptor.recipe_id.strip()
        if not recipe_id:
            raise ValueError("Recipe identifier cannot be empty or whitespace.")
        if recipe_id in self._descriptors:
            raise ValueError(
                f"Recipe '{recipe_id}' is already registered in CanonicalRecipeRegistry."
            )
        self._descriptors[recipe_id] = descriptor
        self._runners[recipe_id] = runner

    def get_descriptor(self, recipe_id: str) -> CanonicalRecipeDescriptor | None:
        """Retrieve the metadata descriptor for a registered recipe.

        Parameters
        ----------
        recipe_id : str
            Unique recipe identifier.

        Returns
        -------
        CanonicalRecipeDescriptor | None
            Matching descriptor if registered, else None.
        """
        return self._descriptors.get(recipe_id.strip())

    def get_dependencies(self, recipe_id: str) -> tuple[DatasetId, ...]:
        """Retrieve canonical DatasetId dependencies for a registered recipe.

        Parameters
        ----------
        recipe_id : str
            Unique recipe identifier.

        Returns
        -------
        tuple[DatasetId, ...]
            Ordered tuple of required canonical dependencies.

        Raises
        ------
        UnresolvedRecipeError
            If recipe_id is not registered.
        """
        desc = self.get_descriptor(recipe_id)
        if desc is None:
            raise UnresolvedRecipeError(
                f"Derivation recipe '{recipe_id}' is not registered.",
                recipe_name=recipe_id,
            )
        return desc.dependencies

    def list_descriptors(self) -> tuple[CanonicalRecipeDescriptor, ...]:
        """List all registered canonical derivation recipe descriptors in sorted order.

        Returns
        -------
        tuple[CanonicalRecipeDescriptor, ...]
            Sorted sequence of registered recipe descriptors.
        """
        return tuple(self._descriptors[k] for k in sorted(self._descriptors.keys()))

    def list_recipes(self) -> tuple[CanonicalRecipeDescriptor, ...]:
        """List all registered canonical derivation recipe descriptors in sorted order.

        Returns
        -------
        tuple[CanonicalRecipeDescriptor, ...]
            Sorted sequence of registered recipe descriptors.
        """
        return self.list_descriptors()

    def get_recipe(self, recipe_name: str) -> CanonicalRecipeDescriptor | None:
        """Retrieve the metadata descriptor for a registered recipe by name or ID.

        Parameters
        ----------
        recipe_name : str
            Canonical recipe name or identifier to inspect.

        Returns
        -------
        CanonicalRecipeDescriptor | None
            Matching recipe descriptor if registered, else None.
        """
        return self.get_descriptor(recipe_name)

    def execute_recipe(
        self,
        recipe_id: str,
        inputs: Mapping[DatasetId, pl.DataFrame],
    ) -> pl.DataFrame:
        """Execute a registered derivation recipe over supplied canonical inputs.

        Parameters
        ----------
        recipe_id : str
            Registered recipe identifier.
        inputs : Mapping[DatasetId, pl.DataFrame]
            Map of available canonical dataset frames.

        Returns
        -------
        pl.DataFrame
            Derived canonical DataFrame.

        Raises
        ------
        UnresolvedRecipeError
            If recipe_id is not registered.
        CanonicalProductionError
            If any declared canonical dependency is missing from inputs.
        """
        clean_id = recipe_id.strip()
        desc = self.get_descriptor(clean_id)
        if desc is None:
            raise UnresolvedRecipeError(
                f"Cannot execute unregistered derivation recipe '{clean_id}'.",
                recipe_name=clean_id,
            )

        runner = self._runners[clean_id]
        missing_deps = [dep for dep in desc.dependencies if dep not in inputs]
        if missing_deps:
            missing_names = [d.value for d in missing_deps]
            raise CanonicalProductionError(
                f"Recipe '{clean_id}' requires missing canonical datasets: {missing_names}.",
                dataset_id=desc.target_dataset_id,
            )

        return runner(inputs)


_GLOBAL_RECIPE_REGISTRY = CanonicalRecipeRegistry()


def get_global_recipe_registry() -> CanonicalRecipeRegistry:
    """Retrieve the global CanonicalRecipeRegistry singleton.

    Returns
    -------
    CanonicalRecipeRegistry
        Authoritative global recipe registry.
    """
    return _GLOBAL_RECIPE_REGISTRY
