# Glossary

This glossary standardizes terms that cross architecture, finance, reference, and developer documentation. Definitions describe how Personal Finance ETL uses each term; they are not attempts to settle every possible industry definition.

## Core terms

### Actionable artifact

A discovered source artifact that requires Bronze work in the current run because it is new, changed, re-ingested, or otherwise requires synchronization.

### Artifact

A source or virtual input tracked by the SQLite Control Plane with stable identity, path/hash observations, synchronization state, and lifecycle events.

### Bronze

Persistent source-near DuckDB layer synchronized at file/category level. Bronze preserves complete raw analytical state across runs.

### Canonical fact

Normalized financial evidence or derived fact with stable semantics independent of a vendor/source layout.

### Control Plane

SQLite operational authority for runs, artifacts, snapshots, failures, payloads, lifecycle events, and simulation provenance.

### Data contract

Registry/schema agreement describing a published dataset: physical table, layer, domain, grain, producer, order, and fixed DDL where applicable.

### Deterministic identity

Stable identifier derived from canonical serialization of semantically identifying fields.

### Evidence

Observed source information such as transactions, broker statements, market observations, FX observations, or configuration inputs.

### Full replace

Bronze synchronization mode that drops/recreates the physical table from the current extracted schema and loads the complete actionable dataset.

### Gold

BI-facing presentation layer rebuilt from current canonical analytical state.

### Grain

The semantic meaning of one row, such as Day, Trade, Date-Currency, ISIN-Lot, or FY-SubHead.

### Healing

Recovery behavior that reconciles DuckDB synchronization state with Control Plane authority after divergence or interrupted cross-store completion.

### Incremental Bronze

Synchronization mode that replaces rows associated with actionable source filenames while retaining rows from unchanged files.

### Indicative tax estimate

Analytical estimate derived from available tax-relevant evidence and configured rates; not final statutory tax liability.

### Local currency

Instrument/economic currency in which acquisition, sale, or market value is observed before reporting-currency translation.

### Meta

DuckDB current-state metadata projection containing latest file, row-count, rules, settings, contract, and simulation context.

### Observed state

Financial/source state directly evidenced by an external or canonical source observation.

### Publication order

Registry integer controlling deterministic Silver/Gold table publication sequencing.

### Reconstructed state

Derived financial state calculated from evidence, such as historical US holdings or FIFO lot state; not independent broker observation.

### Reconciliation

Explicit comparison and adjustment provenance when reconstructed investment state differs from observed quantity or cost basis.

### Realized event

Canonical Quant output representing the disposal of quantity from a specific acquisition lot by a specific sale.

### Replay envelope

Fingerprintable set of model/input/rules/registry/seed context used to reason about stochastic run reproducibility under compatible implementation.

### Reporting currency

Currency used for consolidated valuation/analytics, including translated INR values in the current financial model.

### Silver

Canonical analytical layer containing normalized dimensions/facts plus Quant, reconciliation, and tax evidence.

### Snapshot

Content-addressed canonical settings or FinancialRules payload referenced by runs/simulations.

### Source evidence

Raw externally observed or configured information before canonical financial interpretation.

### Stochastic simulation

Probabilistic FIRE/wealth modeling whose run provenance includes seed and fingerprints; distinct from deterministic financial reconstruction.

### Synchronization status

Control Plane state describing whether an artifact still requires Bronze synchronization or is aligned with analytical raw state.

### Virtual artifact

Control Plane artifact representing generated/configuration evidence that does not necessarily correspond to a conventional source file.

## Semantic distinctions that matter

| Do not collapse | Why |
|---|---|
| Evidence vs reconstructed state | One is observed; the other is derived from observations and algorithms. |
| Historical Control Plane vs DuckDB Meta | One retains operational history; the other projects current analytical context. |
| Incremental ingestion vs incremental analytics | Bronze synchronizes incrementally; Silver/Gold rebuild from complete Bronze state. |
| US market reconstruction vs canonical FIFO | Historical holdings reconstruction supports market state; Quant owns canonical acquisition lots and realized disposals. |
| Realized gain vs tax liability | Quant establishes economic realization; Tax normalizes evidence and estimates, not final statutory liability. |
| Deterministic reconstruction vs stochastic replay | Stable financial identity/reconstruction and probabilistic simulation provenance solve different problems. |
| Artifact path vs artifact identity | Location can change; identity/history should survive legitimate renames. |

## Related specifications

- [Data Model](../architecture/data-model.md)
- [Identity and Grain Contracts](identity-and-grain-contracts.md)
- [Financial Model](../finance/financial-model.md)
- [System Architecture](../architecture/system-architecture.md)
