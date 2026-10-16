# Personal Finance ETL — Source Documentation Protocol

> Applies from v9.1.0 onward.

## Module
Every production module has a useful module docstring. Use `Purpose`, `Owns`, and `Does not own` where architectural ownership could be misunderstood.

## Package
Every meaningful `__init__.py` explains package purpose and intended public surface. Use `__all__` where a deliberate API exists.

## Class
Every public class documents:
1. purpose;
2. responsibilities;
3. state/invariants;
4. important dependencies;
5. lifecycle when relevant.

Pydantic/config models may use concise docs focused on policy meaning.

## Function and method
Every public callable documents its contract. Include only useful sections:

```text
Parameters
Returns
Raises
Side Effects
Notes
```

Financially meaningful functions should state grain, units/currency, validity semantics, or ownership where relevant.

## Private callable
Document when financially meaningful, stateful, algorithmically complex, non-obvious, performance-sensitive, or invariant-dependent.

## Avoid
Do not write documentation that merely repeats the symbol name. Documentation must reduce the need for archaeology.

## Maintenance
A change to a public contract, invariant, side effect, or financial meaning updates source documentation in the same commit.
