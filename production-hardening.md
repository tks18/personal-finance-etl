# Personal Finance ETL — Production Hardening Checklist

## Objective

Harden v6 production architecture **without changing the financial methodology or expected analytical outputs**.

The focus is:

```text
Control Plane
+ Lineage
+ Reliability
+ Semantic Cleanup
+ Documentation Runtime
```

---

## P0 — Raw Store as the Control-Plane Source of Truth

Move operational metadata ownership from DuckDB Meta to the SQLite Raw/Control Store.

### Implement

* [ ] Raw Store becomes authoritative for **run tracking**
* [ ] Move/store **Settings snapshots** in Raw Store
* [ ] Move/store **FinancialRules snapshots** in Raw Store
* [ ] Store application/schema/version context with runs
* [ ] Keep DuckDB Meta only as a **read/query-friendly mirror**
* [ ] Ensure DuckDB Meta is never treated as the operational authority

### Target ownership

```text
SQLite Raw / Control Store
├── Raw artifacts & payloads
├── Synchronization state
├── Runs
├── Run stages / failures
├── Settings snapshots
├── FinancialRules snapshots
├── Lineage
└── Version / reproducibility metadata

DuckDB
├── Bronze
├── Silver
├── Gold
└── Meta mirror
```

---

## P0 — Harden Run Tracking

Give every execution a durable `run_id`.

Track at minimum:

* [ ] `run_id`
* [ ] started / completed timestamps
* [ ] run status
* [ ] current/failure stage
* [ ] error type + message
* [ ] application version
* [ ] schema version
* [ ] Settings snapshot ID
* [ ] FinancialRules snapshot ID

Use an explicit lifecycle such as:

```text
STARTED
→ RUNNING
→ COMMITTING
→ SUCCEEDED

or

STARTED / RUNNING
→ FAILED
```

Never mark a run successful before persistence completes.

---

## P0 — First-Class Data Lineage

Stop depending mainly on filenames/inferred names for lineage.

### Raw artifact identity

* [ ] durable `artifact_id`
* [ ] source category/type
* [ ] source URI / relative path
* [ ] content hash
* [ ] size
* [ ] first/last seen run
* [ ] synchronization state

### Track lineage approximately at

```text
Raw Artifact
    ↓
Bronze Dataset / Partition
    ↓
Canonical / Silver Contract
    ↓
Gold Publication
```

Do **not** build expensive row-level lineage unless there is a genuine use case.

Use `run_id` as the operational spine connecting sources, transformations and outputs.

---

## P0 — Per-ISIN Failure Hardening

Investment workers must never silently disappear.

* [ ] Capture failed ISIN
* [ ] Capture stage + exception context
* [ ] Persist failure against the run
* [ ] Default production behaviour: fail the investment stage/run if an ISIN fails
* [ ] Never publish a seemingly complete portfolio after silently dropping an instrument

---

## P1 — Configuration Snapshot Fingerprints

Deduplicate and identify configuration state by content.

### Settings

```text
snapshot_id
content_hash
canonical payload
created_at
```

### FinancialRules

Same pattern.

Then each run references the relevant snapshot IDs.

Where practical also capture:

* [ ] application version
* [ ] Git commit
* [ ] rules/schema version
* [ ] database/schema version

Goal:

> Be able to identify what evidence + configuration + rules + software version produced a run.

---

## P1 — Explicit Data Contract Registry

Remove physical layer/table inference from internal DataFrame names.

Create a lightweight explicit registry containing concepts such as:

```text
contract_id
layer
physical_table
domain
grain
producer
publication_order
```

Use it where useful for:

* [ ] Silver/Gold publication
* [ ] Meta mirroring
* [ ] row-count tracking
* [ ] lineage
* [ ] layer identification

Keep this lightweight. Do not build a framework around it yet.

---

## P1 — Documentation Runtime Hardening

Remove hard-coded documentation-file lists.

Create one documentation catalog/manifest describing:

```text
section
title
path
order
```

Architecture:

```text
/docs
  ↓
Docs Catalog
  ↓
Markdown Loader
  ↓
Renderer
  ↓
CLI / GUI
```

### Requirements

* [ ] CLI and GUI use the **same catalog**
* [ ] Renderer does not know individual documentation filenames
* [ ] Navigation order comes from manifest/catalog
* [ ] Markdown remains the authoritative content
* [ ] Adding a new document should require minimal/no renderer code change

Design it so the future Wiki/navigation tooling could also reuse the catalog.

---

## P1 — Semantic Cleanup

### Rename misleading fields

* [ ] `Outperformance_Probability` → methodology-accurate name such as `Outperforming_Lot_Ratio`
* [ ] Review `ISIN_Monthly_Return`
* [ ] Either rename it to accurately represent market-value change or implement a true cash-flow-adjusted monthly return

Update all downstream references consistently.

---

## P1 — Externalize Rebalance Policy

Move the current ~5 percentage-point hard-coded rebalance threshold into `FinancialRules`.

Conceptually:

```text
portfolio_management:
    rebalance_tolerance_pct_points: 5.0
```

Keep the existing production value as the default so outputs remain unchanged.

---

## P1 — Remove Residual Pruned Risk Calculations

Audit remaining computation for metrics no longer published/used, especially:

* [ ] Sharpe
* [ ] Sortino
* [ ] Calmar
* [ ] Beta
* [ ] Tracking Error
* [ ] Capture ratios
* [ ] CVaR / Expected Shortfall

If nothing downstream consumes them, remove the computation and associated plumbing.

Do **not** remove Max Drawdown because it remains part of the current serving model.

---

## P2 — Assumption Provenance

Only tackle this today if the earlier work is complete.

Long-term modelled values could identify provenance such as:

```text
OBSERVED
CONFIGURED
REFERENCE
FALLBACK
RECONCILED
ESTIMATED
SIMULATED
```

Useful especially for tax, market, reconciliation and FIRE assumptions.

This is optional for today's hardening.

---

# Final Production Validation

After implementing the changes:

* [ ] Run the complete production pipeline
* [ ] Confirm Silver totals/grains
* [ ] Confirm Gold totals/grains
* [ ] Confirm investment positions
* [ ] Confirm FIFO/tax outputs
* [ ] Confirm household net worth
* [ ] Confirm cash-flow reconciliation
* [ ] Confirm FIRE outputs
* [ ] Confirm Power BI still consumes the warehouse
* [ ] Confirm CLI docs work
* [ ] Confirm GUI docs work
* [ ] Force one controlled failure and verify run/error tracking
* [ ] Confirm Raw Store can explain the complete run lineage
* [ ] Confirm DuckDB Meta mirror agrees with Raw Store control state

## Golden rule

```text
Production hardening
≠
Financial methodology redesign
```

Unless intentionally fixing a known bug, the hardened version should reproduce the current financial outputs.

---

# Definition of Done

Today's hardening is complete when:

> **SQLite is the authoritative evidence/control/lineage plane, DuckDB is the analytical plane, failures cannot silently disappear, configuration and run provenance are traceable, analytical contracts are explicit, documentation discovery is no longer hard-coded, and current production financial results still reconcile.**

Then freeze the version and send the complete repository ZIP for the post-hardening archaeology + documentation pass.
