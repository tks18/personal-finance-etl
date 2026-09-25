# Roadmap

The roadmap is not a promise to turn Personal Finance ETL into every possible finance product.

The direction is narrower:

> **Preserve the working financial system, make its assumptions increasingly explicit, and extract portability only where the production behaviour supports it.**

The current system is the behavioural baseline.

---

## Where the project is now

The current architecture already has:

```text
authoritative SQLite Control Plane
raw evidence persistence
change-aware source synchronization
persistent Bronze
canonical financial contracts
FIFO / tax / benchmark analytics
household wealth and cash reconciliation
FIRE modelling
20 Silver contracts
17 Gold marts
lean DuckDB Meta
CLI + desktop + Power BI
manifest-driven packaged documentation
```

The 6.2.x production-hardening cycle materially strengthened the operating shell without changing the financial truth I rely on.

---

## Roadmap philosophy

```mermaid
flowchart LR
    PROD["Working Behaviour"] --> OBS["Characterize"]
    OBS --> ASSUME["Identify Hidden Assumption"]
    ASSUME --> BOUND["Extract Boundary"]
    BOUND --> ROUTE["Route Current Environment Through It"]
    ROUTE --> REC["Reconcile Financial Truth"]
    REC --> ADOPT["Adopt Generalized Path"]
```

I do not want to replace a working vertical system with a theoretically elegant framework whose behaviour is harder to trust.

---

## 1. Complete the Documentation v2 knowledge system

The repository documentation is being rebased around a stronger editorial model:

> **Explain less. Show more. Prove the architecture with production code. Connect the pieces with diagrams. Use prose for reasoning code cannot communicate.**

The remaining documentation programme is:

```text
Documentation v2
      ↓
full cross-document QA
      ↓
GitHub Wiki
      ↓
repository metadata polish
```

The Markdown docs remain authoritative.

The Wiki will become a guided exploration layer rather than a second competing knowledge base.

---

## 2. Build the Wiki as a knowledge layer

The Wiki should answer journeys such as:

```text
How does one source artifact become a dashboard?
How does a purchase become a tax lot?
How does broker reconciliation affect current state?
How does investment tax flow into household wealth?
How does household wealth flow into FIRE?
```

It should use:

```text
visual explanations
selected production evidence
guided reading paths
links into canonical /docs
```

rather than copying the entire docs tree.

---

## 3. Repository information polish

After the Wiki, the surrounding repository metadata should catch up with the maturity of the implementation.

Targets include:

```text
pyproject.toml
package.json
version_info.txt
GitHub repository description
topics / package metadata
other distribution-facing text
```

Older "hyper-optimized quant engine" style descriptions should give way to language that accurately represents the current financial/data platform.

---

## 4. Coordinated system snapshots

The current snapshot utility protects DuckDB.

The architecture now has two important persistence planes:

```text
SQLite Control Plane
+
DuckDB analytical warehouse
```

A stronger backup/snapshot model would protect them as one coordinated bundle.

Conceptually:

```text
snapshot/
├── Raw_Documents.sqlite
└── Personal_Finance_DB.duckdb
```

This better reflects current ownership.

---

## 5. Deeper normalized lineage

The Control Plane already tracks:

```text
artifacts
payloads
sync state
runs
failures
configuration provenance
execution logs
```

A future lineage expansion could normalize relationships such as:

```text
run
→ source artifacts
→ Bronze partitions
→ Silver contracts
→ Gold contracts
```

Potential structures might include:

```text
run_artifacts
run_stages
run_outputs
lineage_edges
```

This should be added only if the operational value justifies the extra state.

The current system already has strong provenance; it should not be mislabelled as graph-complete lineage before that work exists.

---

## 6. Stronger cross-database recovery semantics

SQLite and DuckDB commits are currently coordinated by the application.

That is appropriate for the current local workload.

Future hardening can explore recovery markers/commit reconciliation around the narrow case where one database commits and the other does not.

I do **not** currently see a need to introduce distributed transaction infrastructure.

The goal would be better local recovery semantics, not architectural theatre.

---

## 7. Continue extracting source adapters

The largest portability constraint remains source specificity.

The long-term direction is:

```text
Source
   ↓
Adapter / Extractor
   ↓
Canonical Financial Contract
```

New source support should increasingly require:

```text
new adapter
new mapping/reference state
```

rather than downstream engine changes.

The canonical financial model should remain stable.

---

## 8. Continue extracting behavioural strategies

Some variation is not configuration.

Examples can include:

```text
different asset accounting behaviour
different tax jurisdiction methodology
different reconciliation policy
different withdrawal methodology
```

Those should become explicit strategies/pipelines when real variation exists.

The rule remains:

```text
same algorithm, different value
→ configuration

different algorithm
→ strategy
```

---

## 9. Preserve the current environment as the regression oracle

Generalization should always route the current production environment through the new abstraction.

Then compare:

```text
positions
tax lots
XIRR
wealth
cash flow
FIRE
Gold contracts
```

If behaviour was not intentionally changed, outputs should reconcile.

This is the main guardrail against "generalization" becoming a rewrite.

---

## 10. Broader configuration-led deployment

The eventual target is a user who can describe more of their environment through:

```text
source definitions
mappings
financial classifications
asset behaviour
tax strategy
planning assumptions
```

without editing core pipeline code.

That does not mean zero customization.

A genuinely different institution/jurisdiction can still require a new adapter or strategy.

The goal is **controlled extensibility**, not magical universality.

---

## 11. Improve assumption provenance

A useful future semantic layer could classify analytical values by provenance:

```text
OBSERVED
CONFIGURED
REFERENCE
FALLBACK
RECONCILED
ESTIMATED
SIMULATED
```

That could be especially valuable in:

```text
tax
broker reconciliation
market/reference state
FIRE
```

because it would make epistemic status easier to inspect.

This is a future enhancement, not current behaviour.

---

## 12. Continue performance work only where useful

The 6.2.x hardening cycle already demonstrated a useful rule:

```text
delete unnecessary work
before
micro-optimizing unnecessary work
```

The current production workload moved from roughly **23 seconds** to **14–17 seconds** end-to-end while preserving financial outputs.

Future optimization should remain evidence-driven.

If 17 seconds is operationally fine, complexity added solely to chase a benchmark number needs a strong reason.

---

## 13. Keep the serving layer curated

Gold should not grow because new metrics are easy to calculate.

A new mart/metric should answer:

```text
What decision does this support?
What is its grain?
What methodology does it require?
Can the consumer interpret it safely?
```

The removal of unused legacy risk metrics is the model for future pruning.

---

## 14. Maintain local-first architecture

The current workload does not require cloud infrastructure for core execution.

Local-first remains the default direction because it fits:

```text
privacy
workload scale
Power BI / desktop integration
operational simplicity
```

Cloud services can be introduced when a concrete capability requires them.

Not because architecture diagrams look more impressive with more boxes.

---

## 15. AI/semantic extensions should remain downstream of trustworthy data

My broader engineering interests include semantic/local-AI systems.

For Personal Finance ETL, any future agentic/semantic layer should consume:

```text
reconciled canonical financial state
+
explicit provenance
```

rather than bypassing the financial model and reasoning directly over messy source files.

The order matters:

```text
trustworthy data
→ semantic layer
→ AI interaction
```

not:

```text
AI first
→ hope it reconstructs finance correctly
```

---

## 16. What is intentionally not on the roadmap

I am not currently optimizing for:

- cloud-native multi-tenancy,
- institutional trading execution,
- a universal global tax engine,
- every possible risk metric,
- microservice decomposition,
- distributed processing for its own sake.

Those could be valid goals for a different product.

They are not requirements of this one.

---

## Roadmap success criteria

The project is moving in the right direction when:

1. Financial truth remains trustworthy.
2. New sources require less downstream change.
3. Financial policy becomes more explicit.
4. Behavioural variation has clean boundaries.
5. Provenance improves.
6. Documentation stays synchronized with implementation.
7. BI contracts remain stable and interpretable.
8. Performance remains operationally comfortable.
9. Complexity is added because the workload needs it.
10. The system remains useful to me while becoming easier for others to extend.

---

## Near-term sequence

```text
Documentation v2
        ↓
Full docs QA
        ↓
GitHub Wiki
        ↓
Repository metadata polish
        ↓
Broader portfolio/profile documentation
        ↓
Next production evolution
```

The roadmap remains subordinate to the working system.

The system exists to improve financial understanding and decisions.

Everything else is engineering in service of that.

---

## Related documentation

- [Project Overview](project.md)
- [About Me](about-me.md)
- [Design Decisions](../architecture/design-decisions.md)
- [Developer Guide](../developer/development-guide.md)

[← About Home](README.md) · [← Documentation Home](../README.md)
