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

- [ ] All MF evidence generalized.
- [ ] Excel physical parsing separated from normalization.
- [ ] No artificial Bronze IDs introduced.
- [ ] Protected investment identities unchanged.
- [ ] MF legacy extraction routes removed.
- [ ] Change/rename/recovery proven.
- [ ] Full Shan outputs green.

## 12. Commit boundary

```text
feat(ingestion): generalize mutual-fund evidence
```

## 13. Handoff to Phase 032

Phase 032 may assume the MF family is completely generalized and the investment transform stack has been proven unchanged under generalized evidence. It applies the same discipline to domestic stock evidence.

## Phase completion record

```text
Phase:
Target release:
Files changed:
Schema changed:
Runtime behavior changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Real-data run:
Performance check:
Compatibility path still present:
Old path deleted:
Exit assertions green:
Commit:
```

A phase is incomplete if any required exit assertion is false.
