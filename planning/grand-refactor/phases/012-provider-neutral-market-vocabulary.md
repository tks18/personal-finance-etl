# Phase 012 - Provider-Neutral Market Vocabulary

**Target release:** v9.6.3  
**Expected effort:** 3-4 hours  
**Previous:** Phase 011  
**Next:** Phase 013  
**Risk:** Medium-High

## 1. Outcome

Separate canonical financial/security identity from Yahoo-specific symbol vocabulary. Canonical Silver state must no longer require a field named for a particular market-data provider; Yahoo symbols remain available through an explicit provider/reference mapping used by provider adapters.

## 2. Why this phase exists

Phase 011 removed source-path leakage. Provider vocabulary is the remaining major external-implementation leak identified by the Phase-008 manifest. Generalized sources/providers should not force a future Silver redesign.

## 3. Inherited repository state

Phase 011 guarantees canonical provenance cleanup. Phase 009 guarantees financial classification is source-independent. Current market providers and financial outputs remain unchanged.

Known v9.5.3 anchors include `yF_Ticker` in currency/benchmark/FX Silver state and `YAHOO_TICKER` in investment master/market-sync paths.

## 4. Current codebase anchors

Anchors:
- `domain/market/fx.py`
- `domain/market/benchmarks.py`
- `domain/household/transforms/reference_dimensions.py`
- `domain/investments/transforms/common.py`
- `application/ingestion/market_sync.py`
- `infrastructure/providers/market/benchmark.py`
- `infrastructure/providers/market/currency.py`
- `infrastructure/providers/market/us_market.py`
- `infrastructure/providers/market/common.py`
- CSV mapping providers
- Silver tables `d_Currency`, `f_Currency_FX_Rates`, `d_Investment_Benchmark_Master`, `d_Investment_Master`, `f_Investment_Benchmark_Data` as applicable.

## 5. Exact target state after this phase

Canonical state owns provider-neutral identifiers such as canonical security/instrument/market symbol fields. A provider mapping owns:
```text
canonical instrument/currency/benchmark identity
    -> provider id
    -> provider symbol
```
Yahoo adapter asks the mapping for its Yahoo symbol. Domain code does not ask for `yF_Ticker`.

Exact canonical field names must follow existing vocabulary where a neutral field already exists; do not introduce duplicate `MARKET_SYMBOL`/`TICKER` aliases without tracing current meaning.

## 6. Detailed implementation sequence

### Step 1 - Trace symbol semantics
For every `yF_Ticker`/`YAHOO_TICKER` occurrence, classify it as canonical identifier, provider request symbol, or temporary mapping field.

### Step 2 - Select canonical neutral field
Reuse an existing neutral instrument/security/currency identifier where possible. If a neutral market symbol is required, define it once in the canonical contract.

### Step 3 - Define provider-symbol mapping
Create/extend a reference contract that maps canonical identity to provider-specific symbol keyed by provider. Do not hard-code Yahoo in domain contracts.

### Step 4 - Migrate market provider adapters
Yahoo-specific infrastructure reads its symbol from the provider mapping. Provider request behavior for current Shan data must remain identical.

### Step 5 - Migrate domain/application consumers
`market_sync`, benchmark/FX logic and investment transforms consume canonical identifiers, not Yahoo-named fields.

### Step 6 - Migrate Silver DDL/producers
Replace provider-named canonical columns additively then cut consumers over. Because Silver rebuilds, remove old columns after zero-consumer proof in this same phase if feasible.

### Step 7 - Update Phase-008 manifest
Close provider-metadata rows and add architecture guard preventing provider-named canonical Silver fields.

### Step 8 - Full provider/financial equivalence
Compare provider request symbols, date ranges, returned market rows, valuations and protected IDs.

## 7. Files and symbols in scope

Modify the market/provider/application/domain files identified above, relevant Silver DDL/producers, provider mapping/reference contracts and tests.

Do not redesign HTTP clients, retry/rate-limit logic, cache behavior or provider request observability.

## 8. Cross-cutting impacts

**Persistence:** Silver schema vocabulary may change; no Control Plane migration.

**Identity:** canonical security identity must not become provider symbol identity. Existing deterministic financial IDs unchanged.

**Observability:** provider name/symbol may remain in provider-request diagnostics. That is legitimate provider metadata.

**Performance:** mapping resolution must be vectorized/batched or dictionary-scale, not one provider lookup per row.

**Compatibility:** current Yahoo requests must be identical for Shan data.

## 9. Tests and verification

Required:
- every Yahoo-specific canonical-field occurrence classified;
- provider adapters resolve current symbols identically;
- canonical Silver DDL contains no provider-named field unless manifest explicitly justifies diagnostic metadata;
- FX/benchmark/US market request tests unchanged;
- investment valuation outputs unchanged;
- protected IDs unchanged;
- full Shan run;
- architecture guard against provider-specific canonical vocabulary.

## 10. Explicit non-goals

Do not:
- add a second market provider;
- change Yahoo provider algorithms;
- change benchmark methodology;
- change currency conversion methodology;
- change financial classification;
- touch capability planning.

## 11. Completion checklist

- [x] Canonical identity is provider-neutral.
- [x] Yahoo symbols live in provider/reference mapping.
- [x] Provider requests unchanged.
- [x] Domain/application code uses neutral vocabulary.
- [x] Silver provider residue closed in manifest.
- [x] Financial outputs and IDs unchanged.
- [x] No hot-path N+1 mapping.

## 12. Commit boundary

```text
refactor(market): isolate provider-specific symbols
```

## 13. Handoff to Phase 013

Phase 013 may assume source-path and provider-specific vocabulary have both been removed from canonical Silver semantics. It can therefore finish the remaining manifest-driven canonical vocabulary migration without mixing provenance/provider concerns.

## Phase completion record

```text
Phase: 012 - Provider-Neutral Market Vocabulary
Target release: v9.6.3
Files changed:
  - src/personal_finance_etl/contracts/market.py (new)
  - src/personal_finance_etl/contracts/__init__.py
  - src/personal_finance_etl/contracts/silver_column_dispositions.json
  - src/personal_finance_etl/infrastructure/warehouse/schema/silver.py
  - src/personal_finance_etl/domain/market/benchmarks.py
  - src/personal_finance_etl/domain/market/fx.py
  - src/personal_finance_etl/domain/household/transforms/reference_dimensions.py
  - src/personal_finance_etl/domain/investments/transforms/common.py
  - src/personal_finance_etl/domain/investments/transforms/us_equity.py
  - src/personal_finance_etl/domain/investments/classification.py
  - src/personal_finance_etl/infrastructure/providers/market/symbol_mapping.py (new)
  - src/personal_finance_etl/infrastructure/providers/market/__init__.py
  - src/personal_finance_etl/infrastructure/providers/market/currency.py
  - src/personal_finance_etl/infrastructure/providers/market/benchmark.py
  - src/personal_finance_etl/application/ingestion/market_sync.py
  - src/personal_finance_etl/application/pipeline/execution.py
  - tests/contracts/test_market_symbols.py (new)
  - tests/contracts/test_semantic_inventory.py
  - tests/architecture/test_boundaries.py
  - tests/domain/test_financial_classification.py
Schema changed: YES (dropped 5 vendor columns: yF_Ticker from d_Currency, f_Currency_FX_Rates, d_Investment_Benchmark_Master, f_Investment_Benchmark_Data; YAHOO_TICKER from d_Investment_Master; Silver columns reduced from 522 to 517)
Runtime behavior changed: NO (provider symbols mapped via ProviderSymbolRegistry, requests identical)
Financial formulas changed: NO
Focused tests: tests/contracts/test_market_symbols.py, tests/contracts/test_semantic_inventory.py, tests/domain/test_financial_classification.py
Architecture tests: tests/architecture/test_boundaries.py
Real-data run: PASS (Full Shan 5-phase pipeline completed with 0 errors)
Performance check: O(1) hash lookup via ProviderSymbolRegistry
Compatibility path still present: NO (zero occurrences of yF_Ticker / YAHOO_TICKER in domain)
Old path deleted: YES (5 Silver DDL columns and all domain references removed)
Exit assertions green: YES
Commit: refactor(market): isolate provider-specific symbols
```

A phase is incomplete if any required exit assertion is false.
