# Phase 003 - Typed Dataset Selectors and Source-Dataset Contracts

**Target release:** v9.5.4  
**Expected effort:** 3-4 hours  
**Previous:** Phase 002  
**Next:** Phase 004 - Complete v9.5.3 Topology as Declarative Configuration  
**Risk:** Low  
**Runtime behavior change:** None  
**Schema/persistence change:** None

## 1. Outcome

Allow a configured physical source to declare which PFETL canonical `DatasetId` it supplies and how that dataset is selected physically, using provider-specific typed selectors rather than untyped dictionaries.

At phase end, the configuration model can express: "Source X is SQLite and table Y supplies canonical Dataset Z" or "Source A is Excel and sheet B supplies canonical Dataset C."

## 2. Inherited state

Phase 002 guarantees:
- `SourceId` and `ProviderType` exist;
- `SourceConfig` identifies provider + location;
- no runtime code consumes source configuration.

Phase 001 guarantees canonical `DatasetId`.

## 3. Current v9.5.3 anchors

Physical dataset selection is hard-coded:
- `SQLiteExtractor.extract_base_tables()` knows the five household tables;
- Excel extraction functions are chosen by category in `DataExtractor._extract_excel_statements()`;
- CSV extraction functions are chosen by category/path in `_extract_config_tables()`;
- `locator.py` folder names choose categories.

This phase models selectors only; it does not migrate these implementations.

## 4. Target contracts

Create discriminated selector models.

### `CsvSelector`
Initial responsibility: identify a file-level dataset and bounded parsing options only where already supported/required. Do not add arbitrary parsing knobs preemptively.

### `ExcelSelector`
Must include `sheet_name` when the current/future dataset needs a sheet. Optional header-row behavior may be included only if required by actual current extractors.

### `SqliteSelector`
Must include `table_name`.

Do not allow arbitrary SQL in the initial public contract.

### `SourceDatasetConfig`

```text
source_id: SourceId
dataset_id: DatasetId
selector: CsvSelector | ExcelSelector | SqliteSelector
enabled: bool = True
```

Mapping, normalization, identity and change-policy fields are not added until their dedicated phases unless a typed optional placeholder is required to avoid churn. Prefer not to add `Any` placeholders.

## 5. Validation rules

A selector must be compatible with the provider of its referenced source. Because `SourceDatasetConfig` alone does not own the SourceConfig list, cross-object compatibility belongs in an aggregate/helper validator, not inside infrastructure.

Required semantic checks:
- SourceDatasetConfig references an existing SourceId when evaluated in aggregate;
- DatasetId exists in the canonical registry;
- provider/selector combination is valid;
- duplicate `(source_id, dataset_id)` bindings are rejected;
- selector values are non-empty;
- user cannot invent arbitrary DatasetId.

## 6. Files in scope

### Create/modify
- `config/sources/selectors.py`
- `config/sources/model.py`
- possibly `config/sources/validation.py` if cross-model validation would otherwise bloat models
- focused tests

### Explicitly do not modify
- file providers
- locator
- coordinator
- Settings
- FileHashPolicy / FILE_TYPE_MAP
- Bronze registry
- Control Plane

## 7. Implementation sequence

1. Add selector discriminated union.
2. Add SourceDatasetConfig.
3. Add aggregate validation helper that receives SourceConfig + SourceDatasetConfig collections.
4. Validate provider-selector compatibility.
5. Validate DatasetId against Phase 001 registry.
6. Add duplicate-binding validation.
7. Add serialization tests showing selectors retain their discriminator/type.
8. Add negative tests for Excel selector on SQLite source, unknown SourceId and duplicate binding.

## 8. Data flow

No runtime data flow changes.

Configuration can now model future physical selection:

```text
SourceConfig
  -> SourceDatasetConfig
       -> typed selector
       -> canonical DatasetId
```

## 9. Persistence / identity / provenance / observability

None.

## 10. Compatibility

Legacy categories remain runtime authority. New selector contracts are dormant.

## 11. Tests

At minimum:

```text
SQLite source + SqliteSelector accepted
SQLite source + ExcelSelector rejected
Excel source + ExcelSelector accepted
CSV source + CsvSelector accepted
unknown SourceId rejected by aggregate validation
unknown/unsupported DatasetId impossible/rejected
duplicate (SourceId, DatasetId) rejected
selector serialization round-trip stable
```

## 12. Non-goals

Do not:
- open files;
- inspect sheet/table existence;
- add arbitrary SQL;
- implement mapping;
- implement source planning;
- migrate SQLiteExtractor.

## 13. Completion checklist

- [ ] Three provider-specific selector types exist.
- [ ] SourceDatasetConfig binds SourceId to DatasetId.
- [ ] Cross-model validation exists.
- [ ] No untyped selector dictionary is used.
- [ ] Runtime remains unchanged.
- [ ] Tests and architecture gates pass.

## 14. Commit

`feat(config): add typed source dataset selectors`

## 15. Handoff to Phase 004

Phase 004 may assume PFETL can declaratively express a physical source and bind a provider-specific selector to a canonical DatasetId. It must now prove this vocabulary can represent the entire v9.5.3 external topology without changing runtime behavior.
