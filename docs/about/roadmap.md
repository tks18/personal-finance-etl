# Roadmap

The roadmap is intentionally smaller than the application.

Personal Finance ETL already has the architecture and reliability foundation I wanted from the recent hardening cycles. The next work is about **formalizing financial semantics, building executable regression protection, and then evolving only when real new scenarios justify it**.

```text
v6.5.3
│
├── Architecture / reliability foundation
│   └── current baseline
│
├── Financial Domain Freeze
│   └── next maturity sprint
│
├── QA Expansion
│   └── executable regression protection
│
└── Feature-Driven Evolution
    └── new evidence / scenario / asset / question
```

---

## Where the project is now

The current baseline already includes:

```text
authoritative SQLite Control Plane
persistent raw payloads
16 Bronze contracts
20 Silver contracts
17 Gold marts
5-table DuckDB Meta projection

change-aware synchronization
PENDING_BRONZE replay
artifact-level self-healing
rename identity migration

run lifecycle + structured failures
cross-process forensic logging
compressed execution history

coordinated Snapshot + Restore

FIFO investment lots
broker reconciliation
shadow benchmark portfolios
XIRR / after-tax XIRR
tax-oriented planning state
cash-flow reconciliation
wealth analytics
deterministic + Monte Carlo FIRE

CLI
Desktop
Power BI
offline packaged documentation
```

That is the starting point for this roadmap, not unfinished work.

---

## Roadmap philosophy

```text
Working behaviour
      ↓
Understand the real boundary
      ↓
Formalize it
      ↓
Protect it with tests
      ↓
Extend only when new evidence demands it
```

I do not want roadmap items merely because a larger platform might contain them.

This remains a personal-finance system that I actually use.

Complexity has to earn its electricity bill. 😄

---

## 1. Financial Domain Freeze

The next domain sprint will formalize selected financial semantics that are already exercised in production but deserve clearer boundaries and deterministic treatment.

The scope stays intentionally close to the current portfolio and source evidence.

### Holding and tax classification

I want explicit, tested semantics around the asset classes the application actually needs today, particularly equity/equity-oriented investments and the currently represented debt-oriented cases.

The goal is not to model every Indian financial instrument.

It is to make the current classification path explicit:

```text
Instrument
    ↓
Tax type / subtype
    ↓
Holding treatment
    ↓
Realized / unrealized state
    ↓
Planning guidance
```

Boundary-day behavior and acquisition/realization dates should be deterministic.

### Realized-event durability

Today FIFO creates sale-linked realized state during analytical reconstruction.

The next maturity step is to decide how realized financial/tax history should remain independently queryable when active lots later disappear.

The design should preserve the distinction between:

```text
source transaction evidence
reconstructed lot state
sale-linked realized state
current active inventory
```

without turning the application into a statutory tax ledger.

### Loss treatment

STCL/LTCL treatment should become an explicit state calculation where the current planning model needs it.

That includes supported set-off ordering and any carry-forward behavior that the project intentionally chooses to represent.

The scope should remain guidance-oriented and limited to semantics that materially improve my planning/filing workflow.

### Tax-guidance composition

The current portfolio tax forecast already publishes useful tax-oriented state.

The sprint should reconcile the complete intended composition, including the known current boundary where `Taxable_Interest` is calculated but not included in `Projected_Tax_Bill`.

The output remains:

> **planning and filing guidance**

not:

> **authoritative final tax-return liability**

### XIRR edge semantics

Normal XIRR behavior is already production-used.

The edge contract should distinguish:

```text
valid numerical result
undefined cash-flow pattern
solver/non-convergence failure
```

rather than allowing every edge state to look like an economically meaningful `0%`.

### Reconciliation provenance

Broker reconciliation is valuable because it anchors reconstructed state to current broker state.

The next domain pass should make the evidence boundary even clearer where reconciliation:

```text
creates missing quantity
removes excess quantity
adjusts active cost basis
```

The objective is explainability, not removal of reconciliation.

### Corporate actions

I do not plan to build a general corporate-actions engine without reliable source evidence.

Supported behavior should be documented and tested where current broker data makes it deterministic.

Unsupported or ambiguous events should remain explicit review boundaries.

---

## 2. QA Expansion

The current repository uses production reconciliation, static analysis and a headless execution harness as important validation signals.

The next QA sprint should convert the behaviors I already rely on into repeatable automated protection.

The target is broader than finance alone.

### Financial golden scenarios

Build deterministic synthetic scenarios covering:

```text
buys
multiple FIFO lots
partial sells
full liquidation
holding boundaries
realized / unrealized state
tax-guidance cases
broker reconciliation
XIRR
after-tax return
cash flow
wealth
FIRE inputs
```

The exact suite should be driven by the final Financial Domain Freeze rather than written against assumptions that are still moving.

### Financial invariants

Examples include:

```text
opening quantity
+ buys
- sells
± supported adjustments
=
closing quantity
```

and:

```text
sale proceeds
- disposed basis
=
realized P&L
```

plus appropriate lineage/rebuild invariants.

### Component tests

Protect important boundaries independently:

```text
Control Plane repositories
file synchronization
Bronze replacement
contract registries
canonical transformation
FIFO
investment aggregation
wealth builders
configuration validation
docs catalog / renderer
```

### Integration tests

Exercise complete workflows such as:

```text
source evidence
→ Control Plane
→ Bronze
→ canonical model
→ engines
→ Silver / Gold
→ Meta
```

with deterministic fixture data.

### Reliability and recovery tests

The hardening work should become permanent regression coverage:

```text
stale run recovery
PENDING_BRONZE replay
missing Bronze table
missing artifact partition
rename migration
worker failure propagation
transaction rollback
Snapshot
Restore
failed Restore rollback
```

### Interface and packaging tests

Protect the user-facing shell:

```text
CLI argument paths
configuration loading
headless execution
packaged documentation assets
bundled Mermaid resource
build/package smoke tests
```

GUI logic should be tested where it can be isolated without turning the suite into brittle pixel automation.

### Test fixtures

The current `tests/` configuration fixtures predate parts of the v6.5.x configuration model.

The QA sprint should replace them with intentional fixtures derived from the current `Settings` and `FinancialRules` contracts rather than carrying legacy keys forward.

---

## 3. Reconciliation report

After the financial and QA work, I want one inspectable reconciliation path that can answer:

```text
source evidence
      ↓
investment / household state
      ↓
realized financial state
      ↓
tax-oriented classification
      ↓
planning guidance
```

For a financial result, I should be able to move backward toward the evidence that produced it.

This is decision-support provenance, not a claim that the application replaces filing records or broker/legal documentation.

---

## 4. Feature-driven evolution

After the Domain and QA freezes, the default roadmap becomes intentionally boring:

```text
new real source
        ↓
new adapter / mapping

new real asset scenario
        ↓
new domain semantics

new financial question
        ↓
new analytical contract

new reliability failure
        ↓
new regression test
```

I do not want speculative extensibility to outrun actual use.

---

## 5. Portability when real variation appears

The architecture already has reusable seams:

```text
Control Plane
Bronze registry
canonical contracts
FinancialRules
investment engine
wealth engine
DataContract registry
application facade
documentation runtime
```

Source-specific assumptions still exist around broker/bank formats, mappings, asset behavior, jurisdiction and reconciliation.

Those should become more portable when a second real environment demonstrates the variation.

The rule remains:

> **Generalize from working behavior, not imagined universality.**

---

## 6. Performance only where it matters

The current production workload is already operationally comfortable.

Future optimization should begin with:

> **Should this computation exist?**

before:

> **How do I make it 8% faster?**

Performance work remains evidence-driven and must preserve intended financial outputs.

---

## 7. Keep the serving layer curated

Gold should remain decision-oriented.

A new metric should answer:

```text
What decision does this support?
What is its grain?
Is it additive?
Can Power BI consume it safely?
Does it justify its production cost?
```

If not, it probably does not belong in Gold.

---

## 8. Local-first remains the default

The core system remains local because that fits:

```text
financial privacy
embedded databases
desktop / CLI workflows
Power BI
offline documentation
low operating cost
```

Cloud infrastructure should enter only if a future requirement actually needs it.

---

## 9. Semantic / AI extensions remain downstream

Local semantic or agentic capabilities remain interesting future possibilities, but they are downstream consumers of trustworthy financial state.

The order stays:

```text
evidence
→ canonical finance
→ reconciled analytics
→ tested contracts
→ semantic layer
→ AI interaction
```

Not the reverse.

There is no reason to give an agent a beautifully conversational interface to financially ambiguous data. 😄

---

## What is intentionally not on the roadmap

I am not currently planning to turn Personal Finance ETL into:

```text
a universal tax-return engine
a brokerage execution platform
a cloud data platform
an institutional risk system
a general accounting ERP
a framework for every asset class
```

Those would be different products.

---

## Roadmap success criteria

The next maturity cycle is successful when:

1. Current financial semantics are explicit at the boundaries that matter.
2. Known guidance limitations are narrow and explainable.
3. Golden financial scenarios protect the intended behavior.
4. System/recovery regressions are automated.
5. Rebuilds from the same evidence and rule version are deterministic where expected.
6. Financial results can be traced backward through the model.
7. `/docs`, Wiki and README remain synchronized without duplicating jobs.
8. New features can return to being driven by real scenarios rather than hardening debt.

---

## Near-term sequence

```text
v6.5.3 documentation rebase
        ↓
Wiki 2.0 guided-learning rebase
        ↓
Financial Domain Freeze
        ↓
QA Expansion
        ↓
final methodology / documentation delta
        ↓
feature-driven evolution
```

That sequence is intentionally finite.

The goal is not permanent hardening.

The goal is to reach a point where the architecture, domain model and tests are stable enough that future releases mostly exist because **something genuinely new happened**.

---

## Related documentation

- [Project Overview](project.md)
- [Financial Model](../finance/financial-model.md)
- [Tax Methodology](../finance/tax-methodology.md)
- [Reliability & Recovery](../architecture/reliability-and-recovery.md)
- [Development Guide](../developer/development-guide.md)

[← About Home](README.md) · [← Documentation Home](../README.md)
