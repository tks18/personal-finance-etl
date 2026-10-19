# Glossary

This glossary fixes the vocabulary used across Architecture, Finance, Developer, Configuration, and Reference documentation.

The terms are intentionally narrow. In a system that distinguishes evidence, reconstruction, reconciliation, estimates, and simulation, “basically the same thing” is how semantic debt gets a mortgage.

## Core terms

### Actionable artifact

A registered source artifact whose current lifecycle state requires Bronze synchronization, healing, or another explicit processing action.

### Artifact

A source evidence object tracked with stable file identity, observed path/hash, lifecycle state, and optional retained payload.

### Bronze

Source-shaped DuckDB evidence synchronized from registered artifacts/providers before canonical financial transformation.

### Canonical fact

A normalized financial record whose meaning and grain are defined independently of presentation.

### Control Plane

SQLite operational authority for run history, artifacts, payloads, configuration/rules snapshots, failures, synchronization, provider requests, and simulation provenance.

### Data contract

A declared agreement covering physical table, layer, domain, grain, producer, publication order, and where applicable schema/identity semantics.

### Deterministic identity

A stable namespace-prefixed SHA-256-derived identifier generated from canonicalized, ordered identity fields.

### Evidence

Observed input from files, databases, providers, configuration, or other external sources before interpretation into canonical/reconstructed financial state.

### Full replace

Bronze synchronization mode where the current complete source state replaces the table state for that contract.

### Gold

Decision-ready analytical presentation layer built from canonical/reconstructed upstream state.

### Grain

The economic meaning of one row, such as one trade, one lot, one realized event, or one Date-ISIN valuation.

### Healing

Recovery action that repairs missing/incomplete synchronized state from retained or rediscovered evidence without pretending the original failure never occurred.

### Incremental Bronze

Synchronization mode that preserves accumulated evidence and incorporates newly discovered artifacts without full table replacement.

### Indicative Tax estimate

A planning/reconciliation estimate derived from configured rules and evidence; not a statutory filing determination.

### Local currency

The instrument/transaction currency used for local-market economics before reporting-currency conversion.

### Meta

DuckDB current-context tables used for analytical inspection; not historical operational authority.

### Observed state

State supported directly by source evidence such as broker holdings or transaction records.

### Publication order

Registry ordering used to respect analytical dependency when Silver/Gold contracts are materialized.

### Reconstructed state

Financial state derived deterministically from canonical evidence, such as FIFO lots or reconstructed holdings.

### Reconciliation

Comparison between independently observed state and reconstructed state, with explicit discrepancy/correction evidence.

### Realized event

A disposal-to-consumed-lot economic event produced by FIFO, preserving acquisition lineage and realized gain/loss context.

### Replay envelope

The evidence, policy snapshots, identity rules, and execution context required to meaningfully reproduce/recompare a deterministic run.

### Reporting currency

The common/base currency used for consolidated analytics after explicit FX conversion.

### Silver

Canonical analytical layer containing normalized dimensions/facts and reconstructed financial events/state.

### Snapshot

Captured durable database/configuration state used for backup, restore, or reproducibility workflows.

### Source evidence

Raw external observations that are retained or normalized before domain interpretation.

### Stochastic simulation

Forward-looking modeled paths that use deterministic seeding for reproducibility but represent uncertainty rather than replay of historical truth.

### Synchronization status

Operational state describing whether an artifact requires Bronze processing, has synchronized successfully, is deferred, failed, or otherwise needs action.

### Virtual artifact

A logical evidence object tracked operationally even when it is not represented by a conventional persisted source file.


## Semantic distinctions that matter

| Do not collapse | Why |
|---|---|
| evidence vs canonical fact | normalization adds meaning |
| observed vs reconstructed | one is sourced; one is derived |
| reconstructed vs reconciled | reconciliation explicitly incorporates discrepancy evidence |
| current Meta vs historical Control Plane | convenience projection is not operational history |
| local vs reporting currency | FX is part of economics, not formatting |
| zero vs null vs invalid | zero is a value; the others describe missing/unsupported state |
| deterministic replay vs stochastic reproducibility | same inputs should reproduce deterministic state; simulation uses seeded modeled uncertainty |
| indicative Tax estimate vs statutory liability | planning evidence is not a filed legal determination |

## Related specifications

- [Financial Model](../finance/financial-model.md)
- [Metrics & Methodology](../finance/metrics-and-methodology.md)
- [System Architecture](../architecture/system-architecture.md)
