# Phase 002 - Source Identity and Provider Contracts

**Target release:** v9.5.4  
**Expected effort:** 3-4 hours  
**Previous:** Phase 001  
**Next:** Phase 003 - Typed Dataset Selectors and Source-Dataset Contracts  
**Risk:** Low  
**Runtime behavior change:** None  
**Schema/persistence change:** None

## 1. Outcome

Introduce typed `SourceId` and `ProviderType`, plus the first versioned `SourceConfig` model, so PFETL can describe a physical evidence source independently of today's category strings such as `sqlite_source`, `mf_orders` and `stock_pl`.

This phase defines source-level vocabulary only. It does not yet describe individual tables/sheets/datasets inside a source and does not change discovery/extraction.

## 2. Why this phase follows Phase 001

A future configured source must ultimately declare which canonical `DatasetId` values it can satisfy. Dataset identity therefore had to exist first.

Current v9.5.3 categories overload source identity and provider type. Phase 002 separates those concepts before selectors and dataset bindings are introduced.

## 3. Inherited state

Phase 001 guarantees:
- `DatasetId` exists and is registry-backed;
- all current Bronze/Silver/Gold contracts have stable IDs;
- legacy extraction/category/runtime behavior is unchanged.

Current v9.5.3 source identity is still implicit in:
- `Settings` path fields;
- `locator.py` category strings;
- `_inject_configuration_assets()` categories;
- `FILE_TYPE_MAP`.

## 4. Target state

Create stable source vocabulary:

```text
SourceId       stable configured source identity
ProviderType   CSV | EXCEL | SQLITE initially
SourceConfig   user-authored source-level configuration
```

Conceptual `SourceConfig`:

```text
source_id: SourceId
provider_type: ProviderType
location: str/path-like configuration value
enabled: bool = True
description: str | None = None
```

Do not include dataset selectors, mappings, identity or capability fields yet.

## 5. Files and symbols in scope

### Create
- `src/personal_finance_etl/contracts/sources.py`
- a source-config package under `src/personal_finance_etl/config/` consistent with project conventions, e.g. `config/sources/model.py`

### Modify
- curated `__init__.py` exports only where appropriate
- focused configuration/contract tests
- architecture-boundary tests if needed to lock dependency direction

### Explicitly do not modify
- `Settings` fields
- `FileHashPolicy`
- `FILE_TYPE_MAP`
- `locator.py`
- `PipelineExecutor`
- `DataExtractor`
- providers
- Control Plane
- warehouse contracts beyond importing `DatasetId` already completed in Phase 001

## 6. Contract design

### `SourceId`

Use a validated/string-backed stable identifier. Requirements:
- serializable as a simple string;
- no filesystem path embedded in identity;
- no provider type embedded in identity;
- same provider type may be used by many SourceIds.

Examples for tests may include `household_db`, `mf_holdings_source`, etc., but do not hard-code Shan-specific IDs into provider infrastructure.

### `ProviderType`

Initial closed vocabulary:

```text
CSV
EXCEL
SQLITE
```

Do not add Parquet merely because internal provider-generated artifacts may use it. Public source-provider vocabulary should reflect externally supported source configuration, not every internal storage format.

### `SourceConfig`

Use Pydantic because this is user-authored validated configuration.

Validation at this phase:
- non-empty source ID;
- supported provider type;
- non-empty location for enabled sources;
- `enabled` defaults true.

Aggregate uniqueness is deferred until the root configuration aggregate exists. Unit tests may use a temporary list validator/helper if needed, but do not create the full root model early.

## 7. Dependency direction

- `config` may import `SourceId`/`ProviderType` from `contracts`.
- `contracts` must not import Pydantic source configuration.
- infrastructure providers must not import `SourceConfig` yet.
- application runtime must not consume it yet.

## 8. Implementation sequence

1. Add `SourceId` and `ProviderType` to `contracts/sources.py`.
2. Add `SourceConfig` in `config/sources/model.py` (or the closest project-conforming path).
3. Add serialization/round-trip tests.
4. Add tests proving two SourceIds may share `ProviderType.EXCEL`.
5. Add tests proving SourceId is independent of path/provider.
6. Add architecture test if necessary to prevent contracts depending on config/infrastructure.
7. Do not wire to Settings or pipeline.

## 9. Before -> after

```text
Before
"mf_orders" means source-ish identity + dataset-ish identity + Excel format

After
SourceId("...") identifies a source
ProviderType.EXCEL identifies physical provider
legacy "mf_orders" remains untouched for runtime compatibility
```

## 10. Persistence / identity / provenance / observability

None. These are configuration contracts only.

No Control Plane schema change and no new event code.

## 11. Tests

Required:
- SourceId serialization stability;
- ProviderType round-trip through Pydantic;
- enabled default;
- enabled source with empty location rejected;
- two Excel SourceConfigs with different SourceIds accepted;
- changing location does not change SourceId value;
- no import-boundary regression.

## 12. Compatibility

All v9.5.3 source categories remain authoritative at runtime. The new contracts are dormant foundation types.

## 13. Delete / retain

Delete nothing.

## 14. Non-goals

Do not:
- define sheet/table selectors;
- move source paths out of Settings;
- create SourceConfiguration root model;
- change file discovery;
- change hashing;
- create provider registry.

## 15. Completion checklist

- [ ] `SourceId` exists and is provider/path independent.
- [ ] `ProviderType` contains only supported external source providers.
- [ ] `SourceConfig` is Pydantic-validated and serializable.
- [ ] Dependency direction is preserved.
- [ ] Runtime code remains untouched.
- [ ] Focused tests pass.
- [ ] Architecture tests pass.

## 16. Commit

`feat(config): add source identity and provider contracts`

## 17. Handoff to Phase 003

Phase 003 may assume:
- DatasetId exists;
- SourceId and ProviderType exist;
- SourceConfig can identify a physical source;
- runtime discovery still uses v9.5.3 categories;
- no source can yet declare which table/sheet supplies a DatasetId.
