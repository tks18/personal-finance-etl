# Phase 001 - Canonical Dataset Identity and Registry

**Target release:** v9.5.4  
**Expected effort:** 3-4 hours  
**Previous:** v9.5.3 baseline  
**Next:** Phase 002 - Source Identity and Provider Contracts  
**Risk:** Low  
**Runtime behavior change:** None  
**Schema/persistence change:** None

## 1. Outcome

Introduce a stable typed `DatasetId` for every existing Bronze, Silver and Gold contract, add deterministic registry lookup/validation around it, and make registry fingerprinting aware of logical dataset identity without changing any frame key, physical table, extraction path or financial output.

At the end of this phase, PFETL can identify a dataset independently of `ExtractionResult` attribute names, `contract_id` strings and DuckDB table names.

## 2. Why this phase is first

Every later generalized source, capability, validation and execution-plan contract needs a stable dataset identity. v9.5.3 currently overloads:

- `BronzeDataContract.extraction_attribute` for Bronze logical identity;
- `DataContract.contract_id` for analytical logical identity;
- physical table names for persistence identity.

Changing source architecture before separating these identities would reproduce the same coupling under new names.

## 3. Inherited state

From v9.5.3:

`infrastructure/warehouse/contracts.py` defines:

```python
@dataclass
class DataContract:
    contract_id: str
    layer: str
    physical_table: str
    domain: str
    grain: str
    producer: str
    publication_order: int

@dataclass
class BronzeDataContract:
    extraction_attribute: str
    sync_category: str
    physical_table: str
    is_full_replace: bool
```

`BRONZE_CONTRACT_REGISTRY` has 20 entries. `DATA_CONTRACT_REGISTRY` contains the fixed Silver/Gold analytical universe.

`infrastructure/warehouse/registry.py` validates current IDs/tables and supports lookup by physical table only.

`infrastructure/warehouse/fingerprints.py::generate_contract_registry_fingerprint()` hashes supplied structural metadata sorted by `table_name`.

## 4. Target state after Phase 001

Create:

```text
contracts/datasets.py
```

with a typed, string-serializable closed `DatasetId` vocabulary for all currently supported canonical datasets.

Extend contracts additively:

```text
BronzeDataContract
  dataset_id              NEW, authoritative logical identity
  extraction_attribute    RETAIN, compatibility/runtime transport
  sync_category           RETAIN, current sync ownership
  physical_table          RETAIN
  is_full_replace         RETAIN

DataContract
  dataset_id              NEW, authoritative logical identity
  contract_id             RETAIN, current frame/runtime key
  layer                   RETAIN
  physical_table          RETAIN
  domain                  RETAIN
  grain                   RETAIN
  producer                RETAIN
  publication_order       RETAIN
```

No current consumer is required to switch lookup keys today.

## 5. Files and symbols in scope

### Create
- `src/personal_finance_etl/contracts/datasets.py`

### Modify
- `src/personal_finance_etl/infrastructure/warehouse/contracts.py`
- `src/personal_finance_etl/infrastructure/warehouse/registry.py`
- `src/personal_finance_etl/infrastructure/warehouse/fingerprints.py` only if needed to include stable dataset identity in the metadata fingerprint path
- `src/personal_finance_etl/contracts/__init__.py` only if this package deliberately exports public contract symbols
- focused tests, preferably existing contract/constitutional test modules rather than a redundant test universe

### Explicitly do not modify
- `contracts/extraction.py`
- `application/ingestion/coordinator.py`
- `application/pipeline/execution.py`
- `infrastructure/warehouse/bronze.py`
- Silver/Gold DDL
- domain financial code
- Control Plane schema

## 6. DatasetId design rules

Use a string-backed enum/value vocabulary suitable for TOML/JSON/Pydantic serialization later.

Names must describe dataset meaning, not dataframe prefixes. Do not use `df_f_*` as the canonical ID vocabulary.

For Phase 001, map every existing contract. Do not leave a contract without an ID and do not introduce user-extensible arbitrary IDs.

Recommended naming families:

```text
HOUSEHOLD_*       household/reference/transaction evidence and state
INVESTMENT_*      investment evidence/state
MARKET_*          FX/benchmark/market evidence
TAX_*             tax state/surfaces
WEALTH_*          wealth analytical surfaces
FIRE_*            FIRE analytical surfaces
COMMON_*          genuinely cross-domain datasets such as calendar
```

The exact member names chosen today become migration-controlled vocabulary. Review them before committing.

## 7. Implementation sequence

### Step 1 - Add `DatasetId`

Create `contracts/datasets.py` with the typed identifier and all current Bronze/Silver/Gold members.

Requirements:
- values are stable lowercase snake-case strings;
- no duplicate values;
- no physical schema/table prefix in the value;
- no `df_` implementation prefix;
- a member belongs to one logical dataset only.

### Step 2 - Extend `BronzeDataContract`

Add `dataset_id: DatasetId` as the first semantic field.

Populate all 20 registry entries. Preserve the other four values byte-for-byte.

### Step 3 - Extend `DataContract`

Add `dataset_id: DatasetId` and populate every Silver/Gold entry. Preserve `contract_id`, layer, table, domain, grain, producer and order exactly.

### Step 4 - Add DatasetId registry indexes

In `warehouse/registry.py`, add deterministic lookup helpers:

```text
get_contract_by_dataset_id(dataset_id)
get_bronze_contract_by_dataset_id(dataset_id)
```

Keep `get_contract_by_table()`.

Do not remove or reinterpret `contract_id`.

### Step 5 - Strengthen registry validation

Extend validation to assert:
- every contract has a DatasetId;
- DatasetId values are unique across the complete canonical registry unless an explicitly documented cross-layer relationship requires separate IDs;
- no duplicate Bronze DatasetId;
- no duplicate analytical DatasetId;
- existing physical-table uniqueness still passes;
- layer/prefix rules remain unchanged.

### Step 6 - Make fingerprint semantics explicit

Trace the metadata passed from Meta into `generate_contract_registry_fingerprint()`.

If logical dataset identity is not represented, add it to the metadata payload used for fingerprinting. Do not remove physical table/grain/producer fields currently used for structural reproducibility.

The fingerprint may intentionally change once because the contract schema gained stable identity. Update the expected test/fixture deliberately rather than hiding the change.

### Step 7 - Run contract and constitutional tests

Run focused tests first, then the existing architecture/constitutional suites.

## 8. Data flow

Before and after runtime data flow is identical. This phase changes metadata identity only.

```text
Before: extraction_attribute / contract_id -> table
After:  DatasetId + legacy key -> same table
```

## 9. Compatibility state

After Phase 001, three names intentionally coexist:

- `dataset_id`: new stable logical identity;
- `extraction_attribute` or `contract_id`: current runtime compatibility key;
- `physical_table`: persistence identity.

This coexistence is intentional. Later phases migrate consumers gradually.

## 10. Persistence, identity, provenance and observability

- DuckDB DDL: unchanged.
- SQLite Control Plane: unchanged.
- Financial IDs: unchanged.
- Source provenance: unchanged.
- Observability events/context: unchanged.

Do not add DatasetId to observability yet; no runtime path resolves source/dataset plans at this phase.

## 11. Tests

Required assertions include:

```text
all Bronze contracts have DatasetId
all Silver/Gold contracts have DatasetId
len(all dataset IDs) == len(set(all dataset IDs)) under the chosen identity model
get_bronze_contract_by_dataset_id(X) returns the exact existing registry object
get_contract_by_dataset_id(Y) returns the exact existing analytical object
legacy get_contract_by_table() still resolves the same object
all 20 Bronze physical tables unchanged
all Silver/Gold physical tables unchanged
all contract_id values unchanged
validate_registry() succeeds
```

Add a negative fixture proving duplicate DatasetId is rejected.

## 12. Real-data and performance gate

A real financial run is not required because runtime behavior is untouched. If your standard release gate always runs the full pipeline, it should produce no output difference.

No performance benchmark is required.

## 13. Delete / retain

Delete nothing.

Explicitly retain:
- `contract_id`;
- `extraction_attribute`;
- `sync_category`;
- all current table names.

## 14. Non-goals

Do not:
- rename Silver/Gold contracts;
- fix domain taxonomy;
- introduce SourceId;
- modify source configuration;
- change hashing;
- modify ExtractionResult;
- change DDL.

## 15. Completion checklist

- [x] `DatasetId` exists in `contracts`.
- [x] Every Bronze contract is mapped.
- [x] Every Silver/Gold contract is mapped.
- [x] Registry lookup by DatasetId works.
- [x] Duplicate DatasetId validation exists.
- [x] Registry fingerprint semantics are deliberate and tested.
- [x] Existing registry/table/runtime keys are unchanged.
- [x] Focused contract tests pass.
- [x] Architecture/constitutional tests pass.
- [x] Repository is green and committable.

## 16. Commit boundary

Recommended single commit:

`feat(contracts): add canonical dataset identity`

Keep the subject <=80 characters under the project's commit policy.

## 17. Handoff to Phase 002

Phase 002 may assume:
- stable `DatasetId` exists for every current canonical dataset;
- registries resolve by DatasetId;
- legacy runtime keys still work unchanged;
- no source/provider abstraction has been introduced;
- no runtime behavior has changed.
