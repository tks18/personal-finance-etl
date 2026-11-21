# Phase 054 - Investment, Reference and Provider Canonical Evidence Migration

**Target release:** v10.5.0  
**Expected effort:** 5-7 hours  
**Previous:** Phase 053  
**Next:** Phase 055  
**Risk:** Critical

## 1. Outcome

Produce source/provider-neutral canonical investment, instrument, benchmark, FX and market-price evidence through the generic production architecture while retaining the existing investment Silver path as the comparison oracle.

This phase changes Bronze/reference evidence shape, not FIFO/Tax/reconciliation methodology.

## 2. Why this phase exists

Current v10.3.0 investment Bronze still mirrors vendor/source families: MF orders/holdings, domestic stock orders/holdings, US stock transactions, Yahoo ticker mappings and US-specific market price contracts. Silver interprets PURCHASE/REDEEM/BUY/SELL and placeholder rows.

A source-agnostic PFETL core needs canonical evidence families that can be produced from one ledger, separate buy/sell files, multiple brokers or providers without changing financial engines.

## 3. Inherited repository state

Phase 053 guarantees:
- generic binding/route/production/satisfiability architecture is the active household path;
- household source-container Bronze is demolished;
- capability planning can rely on canonical evidence rather than source topology;
- investment/ref/provider path is still v10.3.0-shaped and therefore a stable oracle for this migration.

## 4. Current codebase anchors

Trace:
- MF holdings/orders Bronze contracts and transforms;
- domestic stock holdings/orders Bronze contracts and preparation;
- US stock transaction and price provider paths;
- MF ISIN mapping, benchmark mapping/master, currency/provider mapping and macro parameters;
- provider modules `market/currency.py`, `benchmark.py`, `us_market.py`, `symbol_mapping.py`;
- investment master construction;
- purchase/sale preparation inputs;
- benchmark, FX and foreign-asset capability dependencies;
- protected identity generation downstream of prepared investment evidence.

## 5. Exact target state after this phase

Freeze and produce the canonical evidence families justified by current downstream requirements. Expected targets include:

| Canonical concept | Old source/provider families absorbed |
| --- | --- |
| `INVESTMENT_TRANSACTIONS` | MF orders, domestic stock orders, US stock transactions |
| `INVESTMENT_HOLDINGS` | MF holdings, stock holdings and equivalent external snapshots |
| `INVESTMENT_INSTRUMENTS` | ISIN/name/taxonomy identity evidence currently scattered across mapping/holding/order sources |
| `BENCHMARKS` | benchmark master/reference identity |
| `INSTRUMENT_BENCHMARK_ASSIGNMENTS` if cardinality requires | instrument-to-benchmark mapping currently bundled with unrelated metadata |
| `PROVIDER_SYMBOL_MAPPINGS` | Yahoo/provider-specific symbol columns |
| `FX_RATES` | provider-neutral currency-pair observations |
| `BENCHMARK_PRICES` | provider-neutral benchmark history |
| `INSTRUMENT_PRICES` | generalized market prices, not US-specific table identity |

Resolve `INVESTMENT_MACRO_PARAMETERS` ownership explicitly: keep as canonical evidence only if it represents external observed/configured evidence consumed as data; otherwise move its semantics to the correct FinancialRules/config contract in a later owned step within this phase.

Canonical investment transaction action is established before Bronze. PURCHASE/REDEEM/BUY/SELL source strings do not survive as source semantics.

## 6. Detailed implementation sequence

### Step 1 - Freeze an investment evidence disposition matrix
For every current investment/reference/provider Bronze dataset record: source purpose, current grain, downstream consumers, canonical target, identity behavior and whether it is `MERGE`, `GENERALIZE`, `DECOMPOSE`, `KEEP`, or `REMOVE`.

### Step 2 - Produce canonical investment transactions
Create routes for MF/domestic/foreign transaction sources. Map PURCHASE/REDEEM/BUY/SELL into canonical investment action and filter placeholder/non-record rows before Bronze.

### Step 3 - Prove explicit multi-source UNION
For the Shan configuration assemble MF, domestic stock and foreign transaction fragments into the canonical transaction contract where the target design calls for one dataset. Keep instrument/currency/action fields sufficient for existing purchase/sale reconstruction.

### Step 4 - Produce canonical holdings
Merge holdings snapshots into one source-neutral contract with observed quantity/value/price/currency fields actually required downstream. Do not carry vendor-calculated analytics unless explicitly preserved as observed external evidence.

### Step 5 - Construct canonical instrument reference
Separate instrument identity/taxonomy from broker/provider symbols. Preserve ISIN and other stable identifiers; classify which taxonomy attributes are external evidence versus PFETL-derived enrichment.

### Step 6 - Decompose benchmark/reference bundle
Split benchmark identity/assignment from sector/tax/geography/provider symbol metadata according to actual consumers. Avoid a new catch-all mapping table.

### Step 7 - Isolate provider symbol mappings
Move Yahoo/provider symbols to a provider-neutral mapping contract keyed by canonical instrument/benchmark/currency identity as appropriate.

### Step 8 - Generalize provider market evidence
Produce `FX_RATES`, `BENCHMARK_PRICES` and `INSTRUMENT_PRICES` through provider plans while retaining provider request/provenance outside canonical financial meaning.

### Step 9 - Resolve macro-parameter ownership
Document and implement the exact ownership decision so Phase 059 does not freeze an ambiguous contract.

### Step 10 - Add canonical integrity
Validate transaction/holding instrument references, currency references, benchmark assignment references and provider-symbol targets before Silver.

### Step 11 - Build old/new preparation comparison bridge
Do not switch financial engines. Produce canonical evidence in parallel and create deterministic comparison inputs so Phase 055 can prove protected IDs and financial values before demolition.

### Step 12 - Provider/replay/recovery proof
Provider cache/retry/recovery and source replay must rebuild the appropriate canonical target without source-family hardcoding.

### Step 13 - Real Shan evidence run
Generate the complete canonical investment/reference/provider universe from current evidence while the old investment Silver path remains authoritative.

## 7. Files and symbols in scope

Expected changes:
- investment/reference/market Bronze contracts and adapters;
- Shan routes/production definitions for MF/domestic/foreign evidence;
- provider canonicalization outputs;
- instrument/benchmark/provider-symbol contract ownership;
- canonical integrity definitions;
- comparison fixtures and provider/replay tests.

Do not edit FIFO, Tax formulas or reconciliation algorithms except test harness wiring needed for comparison.

## 8. Cross-cutting impacts

**Bronze/reference schemas:** major additive/replacement candidate set.

**Provider neutrality:** Yahoo/provider names move to provider mapping/provenance, not canonical market DatasetIds/columns.

**Identity:** canonical transaction/holding/instrument identity must remain deterministic while protected PURCHASE/SALE/LOT/etc. identities remain downstream and untouched in this phase.

**Capabilities:** new canonical candidates are exposed to satisfiability, but active investment capability requirements switch only in Phase 055.

**Performance:** multi-source production and provider normalization may add cost; correctness first, Phase 058 owns optimization.

## 9. Tests and verification

Required:
- MF PURCHASE/REDEEM and stock BUY/SELL sources map to the same canonical action vocabulary;
- placeholder rows never enter canonical investment evidence;
- multi-broker/source transaction UNION is explicit and deterministic;
- holdings from different source shapes satisfy one canonical holdings contract;
- instrument identity is independent of Yahoo/provider symbols;
- provider symbol mappings are provider-neutral and target valid canonical entities;
- benchmark identity and assignment cardinality are explicit;
- FX/benchmark/instrument price contracts contain no US/Yahoo-specific canonical naming;
- macro-parameter ownership has one documented authority;
- canonical integrity catches missing instrument/currency/benchmark references;
- source/provider replay rebuilds affected targets;
- provider failure recovery remains correct;
- canonical evidence can be transformed into comparison inputs for old Silver without changing the active financial path;
- full Shan run has no financial-output change yet.

## 10. Explicit non-goals

Do not:
- switch purchase/sale/FIFO/reconciliation/Tax consumers yet;
- delete old MF/stock/US Bronze contracts yet;
- redesign financial instrument taxonomy beyond what current finance requires;
- introduce arbitrary provider plugins/config code;
- optimize market fetch or union performance beyond preventing obvious regressions.

## 11. Completion checklist

- [ ] A consumer-backed disposition matrix covers every current investment/reference/provider Bronze dataset.
- [ ] Canonical investment transactions and holdings are produced from MF/domestic/foreign source families through the generic route/UNION model.
- [ ] Instrument identity/taxonomy is separated from provider-symbol mapping and benchmark assignment with explicit ownership.
- [ ] FX, benchmark and instrument-price evidence is provider-neutral at the canonical boundary.
- [ ] `INVESTMENT_MACRO_PARAMETERS` has one explicit evidence-vs-rules ownership decision implemented and tested.
- [ ] Canonical investment/reference integrity, replay and provider recovery are green.
- [ ] Old and new investment evidence can feed a deterministic comparison harness while old Silver remains authoritative.
- [ ] Real Shan execution produces the full new canonical evidence universe with zero protected financial-output change.

## 12. Commit boundary

Use `pfetl-conventional-commits` to group coherent evidence families and provider/reference ownership changes. A transaction-contract change, reference decomposition, and provider-output generalization need not share one commit if the commit skill identifies safer atomic groups.

## 13. Handoff to Phase 055

Phase 055 receives fully produced canonical investment/reference/provider evidence plus the old investment Silver path as oracle. It must switch financial preparation and capabilities to the canonical evidence, prove exact protected identity/financial equivalence, then delete the old vendor-shaped Bronze path and the migration-only compatibility compiler.

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
Commits:
```

A phase is incomplete if any required exit assertion is false.
