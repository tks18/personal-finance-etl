# Phase 02 — Production-Confidence Test Suite

**Sprint:** 2–3 hours  
**Goal:** delete historical phase/certification tests and replace them with a small suite that proves PFETL's actual financial numbers and end-to-end lifecycle.

## Current evidence

The v11.3.1 repository contains **35** `tests/test_*.py` modules. Many are explicitly named for historical phases (`test_phase3_*` through `test_phase13_*`) or refactor-era certification. Some valuable assertions exist inside them, but the suite is dominated by migration history rather than production-output confidence.

## Target test tree

```text
tests/
├── fixtures/
│   ├── config.toml
│   ├── financial_rules.toml
│   ├── household/...
│   ├── statements/...
│   └── references/...
├── conftest.py
├── test_pipeline_e2e.py
├── test_household_golden.py
├── test_investment_fifo_golden.py
├── test_tax_fx_benchmark_golden.py
├── test_wealth_fire_golden.py
└── test_operational_integrity.py
```

Six test modules is the target. Add a seventh only if one module becomes unreasonably broad.

## Fixture design

Build one deterministic miniature household that exercises every important path with hand-checkable values:

- at least one opening balance;
- active income + passive income;
- core + non-core expense;
- transfer into an investment account;
- Indian investment purchase(s);
- one instrument with at least two purchase lots and a partial sale so FIFO is provable;
- at least one foreign-currency/US position so FX decomposition is exercised;
- benchmark observations;
- a realized STCG/LTCG case or dates chosen to exercise both classifications;
- Tax head mapping;
- enough monthly history for wealth/FIRE calculations without requiring a huge dataset.

Provider/API calls must be fixture-backed or stubbed. Golden tests must not depend on live Yahoo data.

## Required tests

### `test_pipeline_e2e.py`

Run `PersonalFinanceEngine.run_pipeline_sync()` or a `ServiceContainer`-created orchestrator against a temporary database base path.

Assert:

- a Control Plane run is created and terminal status is successful;
- Bronze, all 24 Silver and all 22 Gold physical tables exist after publication;
- selected key tables have expected row counts;
- the run leaves no `RECOVERY_REQUIRED` state;
- Meta snapshots/config fingerprints are present where expected.

Do not assert every column merely to mirror DDL.

### `test_household_golden.py`

Assert exact values for the fixture:

- monthly cash income;
- active/passive split;
- core/non-core expense;
- net cashflow;
- investment flow;
- closing cash/account balance;
- net worth;
- savings/investment rates;
- one budget/expense analytical value whose formula is important.

### `test_investment_fifo_golden.py`

Use a two-lot + partial-sale example and assert exact:

- deterministic Purchase_ID and Sale_ID stability across two identical runs;
- lot IDs;
- FIFO quantity depletion order;
- disposed cost basis;
- remaining quantity/cost basis;
- realized gain/loss;
- open-lot market value;
- reconciliation status if fixture includes broker position evidence.

### `test_tax_fx_benchmark_golden.py`

Assert:

- FX rate used on a known date;
- local/base purchase and close values;
- asset PnL and FX PnL decomposition;
- benchmark buy/close comparison and active return;
- STCG/LTCG classification;
- applied tax rate;
- estimated tax;
- LTCG exemption behavior for a known FY.

### `test_wealth_fire_golden.py`

Assert deterministic values for:

- net worth;
- target FI corpus;
- FI gap/progress;
- savings rate / required rate where available;
- approved v11 metrics such as net-worth attribution and income resilience.

For Monte Carlo, use a fixed root seed and assert deterministic summary statistics/invariants, not thousands of raw path values.

### `test_operational_integrity.py`

Assert:

- JSONL forensic file is emitted and parseable;
- RUN_START and terminal lifecycle event exist with same run ID;
- Control Plane run/sync records are durable;
- snapshot creation and restore round-trip a tiny database pair;
- Settings/FinancialRules fingerprints change when a material field changes;
- protected deterministic IDs remain identical across equivalent reruns.

## Migration from existing tests

Before deletion, salvage only logic that materially helps the six tests above. Useful current sources include:

- FIFO/financial assertions from investment tests;
- v11 analytics formulas from `test_phase9_to_12_gold_and_intelligence.py`;
- observability lifecycle assertions from `test_core_pipeline_observability.py`, `test_forensic_pipeline.py`, and emitter tests;
- operator smoke assertions from `test_phase13_single_command_and_operator_services.py`.

Do not carry phase names or constitutional-history assertions into the final suite.

## Delete after replacement is green

Delete the old `tests/` contents, including `run_headless.py`, old phase fixtures, and all phase/certification modules. Recreate only the target tree.

## Exit criteria

- no `test_phase*` files remain;
- every permanent test verifies a user-important output or operational invariant;
- fixture is fully local/deterministic;
- exact numerical expectations are documented inline next to assertions;
- full test suite is small enough to run routinely before monthly use/releases.
