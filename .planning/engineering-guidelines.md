# Personal Finance ETL --- Engineering Constitution

> **Applies to:** the Grand Refactor and all subsequent production code.

## 1. Constitutional rule --- behavior is frozen

The Grand Refactor changes structure, not financial truth.

Unless approved as a separate functional change, it **MUST preserve**
deterministic identities, source-validation semantics, Bronze
synchronization, canonical transformations, FIFO, realized events,
reconciliation, XIRR/CAGR semantics, benchmarks, FX, Tax semantics,
household/cash-flow/wealth logic, FIRE/Monte Carlo, warehouse contract
meaning/grain, Control Plane lifecycle, snapshot/restore, CLI, and
Desktop behavior.

> **A refactor may change structure. It may not quietly change financial
> truth.**

## 2. Normative language

-   **MUST / MUST NOT** --- required; deviation needs an explicit
    architectural exception.
-   **SHOULD / SHOULD NOT** --- default; deviation needs a clear local
    reason.
-   **MAY** --- optional when it improves the design.

Exceptions must be intentional, local, documented, and justified by a
real constraint.

## 3. Core architecture

### Ownership before organization

Every meaningful module SHOULD answer one sentence: **"This module owns
\_\_\_\_."**

If the answer contains unrelated responsibilities, it is a split
candidate.

### One authoritative owner per truth

Canonical facts have one owner. Quant owns realized investment
economics; Tax consumes Quant realization. Control Plane owns historical
operational provenance; Meta exposes current analytical context.
FinancialRules owns configurable financial policy. Presentation consumes
canonical state rather than recreating it.

### Dependency direction

High-level policy SHOULD depend on stable capabilities rather than
concrete infrastructure when the boundary is meaningful.

``` text
Presentation
     ↓
Application
     ↓
Domain / Contracts

Infrastructure
     ↑ implements required capabilities
```

Dependency inversion is especially valuable for persistence, providers,
orchestration, recovery, and cross-process communication. It is not
required for tiny pure helpers.

### OOP where ownership exists

Use classes for state, lifecycle, invariants, policy, dependencies, or
coordinated side effects.

Use functions for deterministic transformations.

> **OOP where ownership exists. Functional programming where
> transformation exists.**

### Local-first remains a boundary

The refactor MUST NOT introduce remote/cloud dependencies merely to
appear more enterprise-like.

## 4. Packages and modules

Packages MUST represent coherent domains or capabilities. Generic
dumping grounds such as `utils`, `common`, `misc`, `helpers`, or
`services` SHOULD be avoided unless the contents are genuinely cohesive
and cross-cutting.

The current `utils` gravity well MUST be reduced.

Every production module MUST have a useful module docstring. Non-trivial
modules SHOULD document ownership explicitly:

``` python
"""Investment reconciliation.

Owns
----
- Comparison of reconstructed and observed investment state.
- Quantity and cost-basis reconciliation.
- Deterministic reconciliation events.

Does not own
------------
- Source extraction.
- FIFO disposal accounting.
- Tax classification.
- Gold publication.
"""
```

Every meaningful `__init__.py` MUST document package purpose and SHOULD
expose an intentional public surface. Use package imports and `__all__`
where they improve clarity. Consumers SHOULD avoid deep private imports.

## 5. Dependency rules

### Domain

Domain logic MUST NOT depend on Desktop, CLI rendering, concrete
DuckDB/SQLite managers, filesystem implementations, provider SDKs, or
docs rendering.

### Application

Application orchestration MAY coordinate domain engines, providers,
repositories, publication, recovery, and configuration. It SHOULD depend
on stable capabilities instead of uncontrolled concrete fan-out.

`ETLOrchestrator` is a primary refactor target for this reason.

### Infrastructure

Infrastructure owns SQLite, DuckDB, filesystem, provider SDKs,
concurrency mechanics, and snapshot archives. It MUST NOT own financial
interpretation.

### Presentation

CLI/Desktop MUST use the application façade/public API. Presentation
MUST NOT calculate canonical finance, directly mutate Control Plane
state, reconstruct FIFO, reinterpret Tax, or infer machine state from
display text.

The legacy tuple/message status boundary MUST become a typed application
contract.

## 6. Typing

### No unexplained `Any`

`Any` MUST NOT be the default escape hatch.

Every remaining use must belong to a documented category:

``` text
THIRD_PARTY_TYPING_GAP
DYNAMIC_SERIALIZATION_BOUNDARY
UNTYPED_EXTERNAL_BOUNDARY
INTENTIONALLY_HETEROGENEOUS_VALUE
```

Narrow the value immediately after the boundary.

### Stable structures require named contracts

Known domain/application structures MUST NOT cross stable boundaries as
`dict[str, Any]`, `tuple[Any, ...]`, or `list[dict[str, Any]]`.

Use a dataclass, Pydantic model, TypedDict where dictionary semantics
are genuinely required, enum, protocol, or dedicated value object.

The analytics pipeline MUST finish migrating anonymous cash-flow,
terminal-value, realized-event, reconciliation-event, snapshot, and
result dictionaries to named contracts.

### Semantic typing over checker compliance

`dict[str, Any]` may satisfy mypy while communicating no domain meaning.
Type annotations SHOULD make the financial/application shape
understandable without opening implementations.

### Optional

Use `T | None` only when absence is an ordinary valid state. Do not use
`None` to collapse missing, invalid, failed, and not-applicable states.

### Cross-process boundaries

Multiprocessing/thread communication MUST use named typed messages.
Anonymous legacy tuples are prohibited in the final architecture.

### Suppressions

`# type: ignore` MUST be narrow, use an error code where supported, and
include a reason when non-obvious.

## 7. Choosing a contract

-   **Enum** --- closed state vocabulary.
-   **Dataclass** --- lightweight record without external validation
    needs.
-   **Pydantic** --- external/configuration/boundary data needing
    validation or serialization.
-   **Protocol** --- meaningful behavioral capability across an
    architectural boundary.
-   **TypedDict** --- transient mapping-shaped structure when dictionary
    behavior is genuinely required.

Do not create interfaces merely to increase abstraction count.

## 8. OOP and SOLID

### SRP

A class/module MUST have one coherent reason to change. Orchestration +
calculation + formatting, persistence + interpretation, extraction +
provenance mutation, or calculation + publication are split signals.

### OCP

Use stable extension points for **real** variation: providers,
persistence, publication strategies, source-specific ingestion. Do not
build frameworks for hypothetical future variation.

### LSP

Implementations of shared capabilities MUST preserve input, output,
failure, and side-effect contracts.

### ISP

Prefer narrow capabilities over giant repository/service interfaces.

### DIP

High-level orchestration SHOULD depend on capabilities where concrete
coupling harms boundaries. Do not wrap pure helpers in ceremonial
interfaces.

### Composition

Prefer composition. Deep inheritance requires strong justification.

## 9. Functions

A function SHOULD perform one coherent operation.

Guideline:

``` text
<= 40 lines   preferred
40–80         acceptable when cohesive
> 80          review for decomposition
```

This is not a hard limit.

Prefer nesting depth \<= 3 where practical. Use guard clauses, policy
functions, strategies, lookup tables, or pattern matching when they
improve clarity.

Prefer \<= 5 direct parameters. When many parameters describe one
concept, introduce a typed request/context object rather than
`dict[str, Any]`.

Multiple boolean mode flags are a design smell; prefer enums, explicit
commands, strategies, or separate use cases.

Important side effects MUST be clear through naming, contracts, and
documentation.

## 10. Classes

A class must earn state. Create one when it owns state, invariants,
lifecycle, policy, or dependency coordination.

Constructors SHOULD establish valid state and SHOULD NOT perform
expensive I/O or start workflows.

Stable collaborators SHOULD be explicit constructor dependencies.

Builder/processor classes with one enormous `build()`/`process()` method
MUST be reviewed for separable input preparation, domain calculation,
aggregation, validation, and output construction. Do not mechanically
turn every phase into another class.

## 11. Errors, Results, and statuses

Use **exceptions** when an operation cannot fulfill its contract.

Use **Result objects** when multiple expected outcomes must cross a
boundary.

Use **status enums** when the state itself has durable or analytical
meaning.

Use **Optional** only for ordinary absence.

Code MUST NOT infer semantics from display text such as
`if "error" in message.lower()`.

The target architecture SHOULD establish a coherent hierarchy similar
to:

``` text
PersonalFinanceError
├── ConfigurationError
├── SourceError
│   ├── SourceValidationError
│   └── SourceCompletenessError
├── DomainError
│   ├── FinancialInvariantError
│   └── CalculationError
├── InfrastructureError
│   ├── StorageError
│   ├── ProviderError
│   └── SnapshotError
└── RecoveryError
```

Exact names are finalized with the target architecture.

## 12. Financial-domain rules

Financially meaningful populated source evidence MUST be validated
before defaults are applied. Malformed evidence MUST NOT silently become
zero, null, empty, or a plausible default.

Grain is part of every analytical contract. Calculations MUST operate at
the correct economic grain.

Deterministic identity creation MUST remain centralized and versioned.

Reconciliation MUST preserve disagreement rather than rewrite original
evidence.

Scenario state --- future tax-lot, rebalance, stress, ML, or FIRE
scenarios --- MUST remain isolated from canonical state.

## 13. Polars and execution boundaries

Use `LazyFrame` by default for composable transformation pipelines.

Every meaningful materialization SHOULD fit one category:

``` text
PUBLICATION_BOUNDARY
STATEFUL_ALGORITHM_BOUNDARY
THIRD_PARTY_BOUNDARY
SCALAR_EXTRACTION
PROCESS_BOUNDARY
VALIDATION_DIAGNOSTIC
```

Repeated materialization inside one transformation chain is a review
signal.

`collect_schema()` is metadata inspection and is not treated as
equivalent to full eager execution, though unnecessary repetition should
still be avoided.

`to_dicts()`, `rows()`, and `iter_rows()` SHOULD be used only for
stateful algorithms, external/process boundaries, or diagnostics that
genuinely require row materialization.

Avoid Polars → Python → Polars round-trips without a documented reason.

## 14. Documentation

Every production module MUST have a module docstring explaining why it
exists.

Every public class MUST document purpose, responsibilities, important
invariants, non-obvious dependencies, and lifecycle/state behavior where
relevant.

Every non-trivial public callable MUST document purpose, meaningful
parameters, return value, raised exceptions, side effects, and financial
semantics where relevant.

Private helpers need documentation only when behavior, financial
semantics, invariants, edge cases, or algorithms are non-obvious.

Comments explain **why**, not syntax.

Stale docstrings are defects.

A single repository-wide docstring style MUST be selected before
implementation begins.

## 15. Naming

Names MUST communicate architectural/domain role. Use suffixes such as
Repository, Provider, Builder, Calculator, Policy, Validator, Result,
Command, Service, or Orchestrator only when the object actually performs
that role.

Prefer domain language: `RealizedEvent`, `TaxEvent`,
`ReconciliationEvent`, `AcquisitionLot`, `Cashflow`, `TerminalValue`.

Established abbreviations such as ISIN, FX, FIFO, FIRE, XIRR, and CPI
are acceptable. Avoid novel internal abbreviations.

## 16. Configuration and policy

Externally loaded configuration MUST enter through validated typed
models.

Configurable financial interpretation belongs in FinancialRules or
explicit domain policy objects, not scattered through transforms, UI, or
Gold formatting.

Runtime settings and financial policy MUST remain distinct.

## 17. Logging and observability

Logs describe facts. They MUST NOT claim stronger guarantees than state
proves.

Words such as `atomic`, `rolled back`, `recovered`, `validated`,
`complete`, `synchronized`, and `successful` require corresponding
machine state.

Structured state controls behavior; logs explain it.

Logs MUST NOT unnecessarily expose sensitive raw financial data.

## 18. Public API and compatibility

A stable application façade SHOULD remain the primary CLI/Desktop
interface so internals can move without repeatedly rewriting
presentation.

Temporary compatibility adapters MAY exist during migration, but each
MUST document purpose, replacement, and planned removal phase.
Compatibility code must not silently become permanent architecture.

## 19. Migration

The Grand Refactor MUST be incremental. No Big Bang rewrite.

Each batch should:

1.  migrate/decompose one coherent area;
2.  preserve behavior/contracts;
3.  update imports;
4.  update source documentation;
5.  remove superseded code where safe;
6.  validate before the next batch.

Prefer mechanical move/rename before semantic restructuring when that
separation makes failures easier to attribute.

Avoid two independent implementations of the same financial behavior
during migration.

## 20. Explicit exceptions

### Numba / numerical kernels

May remain large/procedural when decomposition harms compilation,
performance, or mathematical readability. Document the exception and
section the implementation clearly.

### Declarative schema catalogs

May be large because size reflects contract inventory rather than
control-flow complexity. Split for ownership/discoverability, not
arbitrary line limits.

### Third-party typing gaps

May use narrow `Any`/ignore annotations at the boundary. Narrow
immediately afterward.

### Stateful algorithms

FIFO and similar chronological algorithms may materialize Polars data
into typed Python records when mutable state is the correct compute
model.

### Generated / temporary compatibility code

May temporarily violate ideal structure when explicitly marked and
scheduled for removal.

## 21. Definition of Done --- refactored module

A module is complete when:

-   ownership is clear;
-   dependencies follow this constitution;
-   stable structures are typed;
-   unexplained `Any` is gone;
-   public API is intentional;
-   complexity is reasonable or an exception is documented;
-   financial behavior is unchanged;
-   materialization boundaries are intentional;
-   errors/results follow the standard;
-   module/class/public-callable documentation is complete;
-   obsolete compatibility code is removed when the migration phase
    permits;
-   static checks pass.

## 22. Definition of Done --- Grand Refactor

### Architecture

-   package structure reflects real domain/application/infrastructure
    ownership;
-   dependency direction is explicit;
-   `utils` contains only genuine cross-cutting utilities;
-   presentation depends on the application façade;
-   orchestration no longer has uncontrolled concrete dependency
    fan-out.

### Typing

-   anonymous stable financial/application dictionaries are replaced
    with named contracts;
-   cross-process messages are typed;
-   every remaining `Any` has a documented boundary reason;
-   strict mypy and Pyright remain enabled.

### Complexity

-   giant workflow methods are decomposed where readability/ownership
    improves;
-   numerical/schema exceptions are documented;
-   classes/functions have coherent responsibilities.

### OOP / SOLID

-   stateful objects own state/invariants;
-   pure transformations remain functional;
-   meaningful boundaries use narrow capabilities;
-   no abstraction exists merely to satisfy a pattern checklist.

### Documentation

-   every production module has ownership documentation;
-   every public class is documented;
-   every non-trivial public callable is documented;
-   meaningful packages explain purpose/public surface.

### Execution

-   Polars materialization boundaries are intentional;
-   unnecessary eager round-trips are removed;
-   performance-sensitive exceptions are documented.

### Behavior

-   v8.3.1 remains the behavioral reference unless a separately approved
    functional change supersedes it.

## 23. Permanent feature gate

Every future feature must answer:

1.  Which package/domain owns it?
2.  What typed contracts cross its boundaries?
3.  Does it introduce a new authoritative financial truth?
4.  What dependencies does it add and in which direction?
5.  Why is each class a class?
6.  Where are materialization boundaries?
7.  How are invalid/failure states represented?
8.  What public API changes?
9.  Are source docs complete?
10. Does it comply with this constitution or document an explicit
    exception?

## 24. Final principle

The Grand Refactor succeeds when an engineer can open an unfamiliar area
and quickly answer:

``` text
What does this package own?
What does this class own?
What shape is this data?
Where did this value come from?
What can fail here?
Why is this dependency allowed?
Where does this state become durable?
What financial truth does this code represent?
```

> **The financial system is already sophisticated. The refactor's job is
> to make the code equally legible.**
