# AGENTS.md — Testing Workspace Guidelines

> **Directory:** `tests/`  
> **Test runner:** Pytest via Astral `uv` (`uv run pytest`)  
> **Target Python:** `>=3.13`

---

## 1. Purpose

The test suite is an executable architectural mirror of `src/personal_finance_etl/`. Tests protect financial correctness, dependency boundaries, persistence/recovery semantics, configuration contracts, source/canonical separation and the active Grand Refactor phase handoff.

Tests must not merely reproduce implementation details. They should encode the invariant that would make a regression dangerous.

---

## 2. Test Tree

```text
tests/
├── conftest.py
├── architecture/      # AST/import/legacy-demolition/product invariants
├── contracts/         # identifiers, DatasetContracts, capability/provenance contracts
├── config/            # Settings, FinancialRules, SourceConfiguration and fingerprints
├── domain/            # pure financial kernels and calculations
├── infrastructure/    # DuckDB, SQLite, providers, validation, observability, persistence
├── application/       # planners, admission, canonical production, replay and orchestration
├── presentation/      # CLI/Desktop/facade behavior
└── fixtures/          # static source evidence/configurations and headless runners
```

Use semantic filenames that describe the subsystem. Do not create phase-numbered test files merely because a test was introduced during a particular phase.

---

## 3. Grand Refactor Test Boundaries

Tests must evolve with the owning phase. Do not assert future architecture before its phase introduces it, but once a phase cuts over an invariant, add a regression guard so later work cannot silently reintroduce the old model.

### Source / canonical identity

After the relevant cutovers, architecture and contract tests must enforce:

- `SourceId` identifies physical source/provider configuration.
- `SourceBindingId` identifies physical tabular streams.
- Pre-Bronze runtime/persistence is binding-keyed, not canonical DatasetId-keyed.
- `DatasetId` names PFETL canonical financial evidence/state only.
- one binding may own multiple routes;
- one canonical dataset may depend on multiple explicit routes/providers/registered recipes;
- no declaration-order or filesystem-order producer selection.

### Semantic interpretation

Once Phase 049 is authoritative, tests must reject configuration/runtime paths that introduce:

- arbitrary Python/eval callbacks;
- SQL predicates/queries as semantic rules;
- user-authored Polars expressions;
- joins/aggregation/windows inside semantic mapping;
- financial formulas in source configuration;
- silent unknown canonical-enum values.

Add focused tests for bounded rule ordering, include/exclude behavior, canonical enum mapping, placeholder/deleted-row filtering and deterministic rule fingerprints.

### Canonical production

Once Phase 050 is authoritative, tests must cover:

- `DIRECT` source production;
- explicit `UNION` across multiple routes;
- provider production;
- registered PFETL-owned derived production;
- post-assembly canonical identity;
- duplicate collision semantics;
- grain/uniqueness enforcement;
- Gate 2 on final assembled canonical datasets;
- canonical cross-dataset integrity before Silver;
- valid-empty vs absent/disabled/malformed distinctions.

Never treat `unique()` / keep-first / keep-last behavior as an acceptable financial duplicate policy unless a DatasetContract explicitly defines the semantics.

### Satisfiability planning

Once Phase 051 is authoritative, tests must prove:

- exactly one resolved producer per required active DatasetId;
- missing producer diagnostics;
- ambiguous producer diagnostics;
- explicit source `UNION` selection;
- optional unsatisfied datasets remain inactive rather than becoming fake empty evidence;
- derived dependency cycle detection;
- deterministic plan/fingerprint behavior;
- stale existing Bronze cannot satisfy missing current configuration.

### Silver source independence

After the household/investment cutovers, architecture tests must prevent Silver/domain logic from interpreting retired source fields or vendor encodings such as historical category/transaction codes, deletion flags, broker action strings, placeholder rows or provider-specific symbol topology.

If financial code needs meaning that only a source field currently supplies, stop and repair canonical evidence ownership rather than whitelisting the source field in Silver.

### Unified contract authority

By Phase 059, tests must prove:

- every Bronze/Silver/Gold DatasetId has exactly one authoritative DatasetContract;
- Pre-Bronze does not pretend to have a global canonical DatasetContract;
- DDL/Pandera/capability-column indexes are derived from DatasetContracts rather than manually duplicated schema lists;
- contract grain, keys and references point to existing columns/datasets;
- base contracts remain immutable while effective contracts reflect the active ExecutionPlan;
- contract serialization/fingerprints are deterministic and implementation-library-neutral;
- physical warehouse schemas match effective contracts in final acceptance.

---

## 4. Financial Regression Oracles

Architecture/schema migration must not silently change PFETL financial truth.

For the Shan baseline and any equivalent external topology, compare protected downstream identities and financially meaningful outputs as required by the active phase.

Protected identity families include:

- `PURCHASE`;
- `SALE`;
- `LOT`;
- `REALIZED`;
- `RECON_LOT_GROUP`;
- `RECON_GROUP`;
- `RECON_EVENT`;
- `TAX`.

Any unexplained ID drift or paise-level value difference is a phase stop unless the phase explicitly documents an intentional representation change outside financial methodology.

Do not fork financial engines merely to compare migration paths. Compare old/new preparation or canonical evidence while reusing the same PFETL-owned financial kernels.

---

## 5. Fixture Governance

Use **static, sanitized evidence fixtures** for ordinary tests. Do not generate fake Excel/CSV evidence dynamically inside test functions when a stable fixture can represent the case.

Fixture coverage should evolve toward topology families rather than Shan-only source names:

```text
tests/fixtures/evidence/
├── shan/                       # regression oracle evidence
├── external_household/        # alternate household topologies
├── external_investment/       # alternate domestic/foreign broker topologies
└── negative/                   # malformed mapping/schema/identity/ambiguity cases
```

Exact folder names may follow the phase implementation, but the ownership rule is fixed: fixtures model evidence/topology, not hidden code branches.

Required external certification coverage eventually includes:

- one physical source -> several canonical datasets;
- several physical bindings -> one canonical dataset through explicit UNION;
- CSV/Excel/SQLite household variants;
- domestic-only and foreign investment variants;
- multiple broker/action vocabularies;
- invalid semantic mapping;
- identity collision;
- missing/ambiguous producer;
- malformed Gate-1 and Gate-2 evidence.

---

## 6. Shared Fixtures and Isolation

Prefer typed shared fixtures in `tests/conftest.py` for Settings, FinancialRules, storage managers, Control Plane, observability and composed application services. Add shared fixtures when a setup pattern is genuinely reused; do not force unrelated topology-specific evidence into one global fixture merely to avoid a few lines.

All standard tests are offline-first and sandboxed under temporary paths. Live user-data tests must be explicitly marked `@pytest.mark.live_data` and excluded from normal CI when appropriate.

Do not access personal cloud mounts, production databases or network services from ordinary unit/architecture tests.

---

## 7. Typing and Test-Code Standards

- Every test function is explicitly typed and returns `None`.
- Avoid `Any` and untyped generic containers when a concrete type can be modeled.
- `# pylint: skip-file`, broad `noqa`, `TYPE_CHECKING` workarounds and inline/deferred imports are forbidden where architecture/quality rules prohibit them.
- Test module docstrings describe ownership and purpose, not historical phase chronology.
- Assert observable contracts/invariants, not incidental private implementation shape unless the test specifically guards architecture.

---

## 8. Phase Verification Discipline

Use the active phase file as the test authority. A phase-specific checklist may require more than the generic repository gate.

Typical focused sequence:

```powershell
uv run pytest tests/<affected area>/...
uv run pytest tests/architecture/test_boundaries.py
uv run poe audit:fast
```

Persistence/cutover phases additionally need the named rollback, replay, backup/restore and existing-state tests. Minor/certification releases additionally require the phase-specified full quality gate, Shan oracle, external fixture, observability and performance checks.

When the environment cannot run a required gate, record it as unverified. Never convert an unavailable runtime check into a claimed pass.
