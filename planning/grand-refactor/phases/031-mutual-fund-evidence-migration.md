# Phase 031 - Mutual-Fund Evidence Migration

**Target release:** v10.0.0-rc4  
**Expected effort:** 3-4 hours  
**Previous:** Phase 030  
**Next:** Phase 032  
**Risk:** High

## 1. Outcome

Migrate all remaining mutual-fund source evidence through the generalized ingestion architecture while preserving the current downstream investment identity and accounting semantics.

At phase end MF holdings/market evidence and MF transaction/order evidence are configuration-driven, validated through Pre-Bronze/canonical Bronze, transported by DatasetCollection, and no MF-specific legacy extraction branch remains.

## 2. Why this phase exists

Mutual funds are the first high-value investment family. Unlike household stable-UID evidence, MF Bronze rows must not be given artificial IDs merely to make ingestion look uniform. PURCHASE/SALE and later lot/reconciliation identities are created only after financial semantics exist.

## 3. Inherited repository state

Phase 030 guarantees:
- DatasetCollection is authoritative;
- household and static/reference evidence are generalized;
- SourceConfiguration is sole mapping authority;
- MF ISIN/reference mapping is already generalized;
- Pre-Bronze/Pandera/recovery patterns are proven;
- fixed investment Excel paths/branches may still exist.

Phase-007 identity requirements remain authoritative.

## 4. Current codebase anchors

At phase start generate the exact MF family table from the current Bronze registry/migration ledger.

Historical anchors include:
- `mf_market_data_raw`
- `mf_transactions_raw`
- categories such as `mf_holdings`, `mf_orders`
- Excel provider extraction functions
- `application/ingestion/asset_strategies.py`
- MF transform modules
- investment master/purchase/sale construction
- ISIN mapping consumer
- protected identity generation in `domain/investments/transforms/common.py`.

Use post-Phase-030 symbols, not stale v9.5.3 field names, where prior phases changed APIs.

## 5. Exact target state after this phase

For every MF evidence DatasetId:
```text
SourceConfig/Excel selector
 -> resolved change policy
 -> Raw artifact
 -> physical Excel extraction
 -> SOURCE validation
 -> Pre-Bronze
 -> configured normalization
 -> Bronze identity policy (NONE unless contract explicitly requires otherwise)
 -> BRONZE validation
 -> canonical Bronze
 -> DatasetCollection
 -> existing MF financial transform
```

MF financial transforms continue to create PURCHASE/SALE identity exactly where they do before this phase.

No legacy folder/category-specific MF extraction branch remains after equivalence.

## 6. Detailed implementation sequence

### Step 1 - Freeze MF migration parameter table
For each MF DatasetId record SourceId, selector/sheet rules, sync strategy, source schema, mapping, Bronze schema/grain, identity requirement and downstream consumer.

### Step 2 - Generalize Excel physical extraction
Any MF-specific provider cleanup that is source normalization moves to configured normalization. Keep only physical workbook/sheet parsing in infrastructure provider.

### Step 3 - Migrate MF market/holdings evidence
Execute Phase-025 template. Validate canonical grain/uniqueness without inventing synthetic row IDs.

### Step 4 - Migrate MF transaction/order evidence
Execute template. Preserve all fields required by existing purchase/sale reconstruction.

### Step 5 - Downstream identity equivalence
Run current MF transforms and compare PURCHASE/SALE IDs byte-for-byte. Then run FIFO/reconciliation and compare LOT/REALIZED/RECON identities.

### Step 6 - Change/rename/rerun semantics
Exercise current MF file policy: unchanged, changed, renamed where supported, removed/full-replace as configured.

### Step 7 - Remove MF-specific legacy routes
Delete category-specific extractor/orchestration branches and any fixed path assumptions used only by MF evidence.

### Step 8 - Family performance/regression
Compare MF row counts, holdings, realized/unrealized values, provider/enrichment inputs and full Shan outputs.

## 7. Files and symbols in scope

Modify:
- MF SourceConfig/dataset contracts;
- Excel provider generic selector path;
- ingestion/source-plan wiring;
- MF-specific legacy extractor branches;
- validation fixtures/tests.

Read but do not change formulas in:
- MF financial transforms;
- FIFO;
- reconciliation;
- Quant/Tax.

## 8. Cross-cutting impacts

**Persistence:** MF Pre-Bronze production state added; Bronze canonical admission strict for migrated MF datasets.

**Identity:** no new Bronze identity unless contract requires it. PURCHASE/SALE/LOT/REALIZED/RECON/TAX IDs must remain unchanged.

**Provenance:** artifact/source/dataset trace preserved across multiple MF files.

**Observability:** events use DatasetId/SourceId; no legacy category required for financial meaning.

**Performance:** Excel parsing and validation overhead measured; avoid repeated workbook parsing for datasets sharing a file where safe.

## 9. Tests and verification

Required per MF dataset:
- source/Bronze validation;
- Pre-Bronze/Bronze row equivalence;
- change/rerun semantics;
- legacy route not called.

Financial:
- MF purchase/sale values identical;
- PURCHASE/SALE IDs identical;
- FIFO lots/realized identical;
- reconciliation identical;
- Tax inputs unchanged;
- full Shan regression.

Architecture:
- no MF folder-name/category branch required for production extraction;
- no artificial MF Bronze identity introduced.

## 10. Explicit non-goals

Do not:
- change MF accounting methodology;
- alter ISIN matching semantics;
- alter FIFO/reconciliation;
- migrate stock/US evidence;
- make capability changes;
- remove global locator yet.

## 11. Completion checklist

- [x] All MF evidence generalized.
- [x] Excel physical parsing separated from normalization.
- [x] No artificial Bronze IDs introduced.
- [x] Protected investment identities unchanged.
- [x] MF legacy extraction routes removed.
- [x] Change/rename/recovery proven.
- [x] Full Shan outputs green.

## 12. Commit boundary

```text
feat(ingestion): generalize mutual-fund evidence
```

## 13. Handoff to Phase 032

Phase 032 may assume the MF family is completely generalized and the investment transform stack has been proven unchanged under generalized evidence. It applies the same discipline to domestic stock evidence.

## Phase completion record

```text
Phase: 031 - Mutual-Fund Evidence Migration
Target release: v10.0.0-rc4
Files changed:
  src/personal_finance_etl/infrastructure/providers/files/excel.py
  src/personal_finance_etl/infrastructure/providers/files/__init__.py
  src/personal_finance_etl/config/sources/selectors.py
  src/personal_finance_etl/config/sources/loader.py
  src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
  src/personal_finance_etl/contracts/canonical_fields.py
  src/personal_finance_etl/application/ingestion/slice_runner.py
  src/personal_finance_etl/infrastructure/warehouse/bronze.py
  src/personal_finance_etl/application/pipeline/execution.py
  src/personal_finance_etl/application/ingestion/coordinator.py
  src/personal_finance_etl/presentation/observability/desktop_sink.py
  src/personal_finance_etl/presentation/observability/cli_narrative.py
  tests/application/test_mutual_fund_evidence_migration.py
  tests/application/test_generalized_vertical_slice.py
  tests/infrastructure/test_admission_contracts.py
  tests/presentation/test_narrative.py
  planning/grand-refactor/phases/031-mutual-fund-evidence-migration.md
  planning/grand-refactor/README.md
Schema changed: Pre-Bronze pre_bronze_market_mf_holdings and pre_bronze_investment_mf_orders schemas introduced; canonical Bronze schemas for both admitted with zero synthetic row UIDs.
Runtime behavior changed: Mutual-fund evidence (market data and transaction orders) admitted exclusively via generalized vertical slice runner; legacy extraction routes removed; physical Excel parsing generalized into ExcelExtractor with sheet selection, anchor detection, and date inference; narrative sinks updated to suppress per-file validation chatter while preserving 100% forensic trace in JSONL.
Financial formulas changed: NO
Focused tests: tests/application/test_mutual_fund_evidence_migration.py
Architecture tests: tests/architecture/test_boundaries.py tests/architecture/test_legacy_demolition.py
Real-data run: Certified with live statement files and full financial output parity.
Performance check: Fast quality gate < 1.0s; full quality gate clean.
Compatibility path still present: Pre-Bronze physical tables preserve provenance without duplicate non-dunder artifact_id.
Old path deleted: Legacy extract_mf_market_data_raw and extract_mf_transactions_raw coordinator branches retired.
Exit assertions green: YES
Commit: v10.0.0-rc4
```

A phase is incomplete if any required exit assertion is false.
