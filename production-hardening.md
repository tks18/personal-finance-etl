# Architecture & Reproducibility Implementation Freeze

> **Status: REBASED IMPLEMENTATION FREEZE | Baseline: v6.6.1**
>
> This is the implementation authority for the Architecture & Reproducibility Sprint. New capabilities belong in a future sprint unless required to implement a frozen contract correctly.

## 1. Artifact lifecycle against runs

### Change

Extend the file registry:

```text
first_seen_run_id / first_seen_at
last_seen_run_id / last_seen_at
last_changed_run_id / last_changed_at
last_synced_run_id / last_synced_at
```

### Implementation

```text
new artifact      → first_seen + last_seen
unchanged         → last_seen only
changed           → last_seen + last_changed
successful sync   → last_synced
PENDING_BRONZE replay without source change → last_synced only
```

### Done when

Current artifact lifecycle is understandable without execution logs.

---

## 2. Historical artifact-run lineage

### Change

Add `cp_artifact_run_events`:

```text
event_id
run_id
file_id
event_type
event_at
observed_path
content_hash
previous_status
new_status
event_reason
```

Event vocabulary:

```text
DISCOVERED
CHANGED
RENAMED
PENDING_BRONZE
SYNCED
HEALED
REMOVED
```

### Implementation

`event_id` identifies the operational occurrence. `event_reason` is short explanatory context. Detailed errors/stacks remain in execution logs.

### Done when

Run → artifacts and artifact → runs are directly queryable.

---

## 3. Rename semantics

Pure rename:

```text
write RENAMED
preserve file identity
migrate path-dependent Bronze/Meta identity
do not mark content changed
```

A rename must never create duplicate financial state.

---

## 4. Dynamic FX and US market source provenance

### Change
Treat fetched currency rates and US market prices as versioned analytical input evidence, not invisible runtime dependencies.

### Impact
An unchanged broker statement can produce different financial results if historical Yahoo Finance data, mappings, or caches change. Existing run and artifact provenance alone cannot explain that difference.

### Implementation
- Reuse existing Currency and US Market extractors, Bronze caches and pipeline orchestration. Do not introduce a new data platform.
- For each refresh, record provider/source, currency pair or ticker, requested range, actual observed range, extraction time, refresh outcome and content fingerprint. Keep historical run provenance in the existing Control Plane, and current data in Bronze/Silver.
- Include the materialized FX and market series actually consumed, currency mappings, and as-of cutoff in the Reproducibility Envelope. A model replay must be able to use cached evidence without requiring a fresh network response.
- Define explicit cache-gap detection for missing interior dates, not merely the latest cached date. Distinguish market closures from missing observations; do not require trading prices on weekends.
- Never label an incomplete fetch as complete merely because a cache file exists. Preserve prior valid cache data on partial fetch failure.

### Done when
A run can explain exactly which FX/US-price observations produced its investment outputs; identical cached inputs reproduce identical outputs offline.

## 5. Currency reference validation and pipeline ordering

### Change
Make currency normalization and historical conversion inputs explicit prerequisites of investment analytics.

### Impact
A missing currency mapping or FX observation can otherwise propagate into FIFO, valuation and Gold as a plausible-looking INR result.

### Implementation
- Preserve the existing `CURRENCY_ID` foreign-key relationship to the currency master across investment facts.
- Define one base/reporting currency, one explicit FX quote direction (reporting-currency units per one local-currency unit), and one identity conversion for genuine base-currency assets only.
- Validate currency IDs, ticker-to-currency mapping, required FX coverage and price coverage before publishing dependent analytical outputs.
- Keep the current order: currency data and US market data prepared before Quant. Ensure failure propagates through the current atomic publication boundary.
- Do not generate `Lot_ID` for source market/benchmark rows. Lot identity remains Quant-owned.

### Done when
Missing or invalid foreign FX data cannot silently publish as a valid 1.0 conversion and currency references are consistent throughout the investment pipeline.

## 6. Identity precedence

Freeze:

```text
stable native identity exists
→ use it

no stable native identity
→ generate deterministic canonical analytical identity
```

Examples:

```text
Investment instrument → ISIN
Household transaction → UID
Canonical purchase → Purchase_ID
Canonical sale → Sale_ID
FIFO lot → Lot_ID
Realized disposal → Realized_Event_ID
Reconciliation → Reconciliation_Group_ID / Reconciliation_Event_ID
Tax event → Tax_Event_ID
```

Do not create unnecessary surrogate IDs.

---

## 7. Canonical ID Serialization v1

All generated deterministic IDs use one shared serialization contract.

```text
Encoding: UTF-8
Field order: explicitly defined by each ID contract
Strings: Unicode NFC; trim outer whitespace; preserve internal whitespace
Case: preserve unless field domain explicitly defines case-insensitivity
Null: <NULL>
Date: YYYY-MM-DD
Datetime: ISO-8601 using application timezone convention
Integer: base-10, no unnecessary leading zeros
Boolean: true / false
Currency: canonical CURRENCY_ID
Numeric: canonical decimal notation; no grouping/exponent; strip insignificant trailing zeros; -0 → 0
Structured serialization: unambiguous field-name + canonical-value representation
```

Therefore:

```text
10 = 10.0 = 10.00
-0 = -0.0 = 0.00 = 0
```

Use one stable cryptographic hash policy and namespaces such as:

```text
PURCHASE
SALE
LOT
REALIZED
RECON_GROUP
RECON_EVENT
TAX
CONTRACT_REGISTRY
```

### Identity contract rule

Changing serialization version, defining attributes, field order, namespace, normalization, or hash policy is an **analytical identity contract change**.

---

## 8. Identity is not provenance

Never use these in deterministic financial identity:

```text
run_id
run timestamp
hostname
temporary path
working directory
process ID
log/output path
```

They remain provenance.

---

## 9. Keep existing canonical investment grain

Do not redesign Bronze or restore source broker-order grain.

```text
Purchase_ID → canonical aggregated f_Investment_Purchase_Data row
Sale_ID     → canonical aggregated f_Investment_Sale_Data row
```

Market and benchmark facts keep their existing grains and do not receive Lot_ID.

---

## 10. Currency-aware analytical identity

### Change
Extend existing deterministic analytical IDs to multi-currency canonical facts.

### Implementation
- Continue to use the native `ISIN` and currency-master `CURRENCY_ID`.
- Canonical Purchase/Sale IDs already include `CURRENCY_ID`; keep it in the defining tuple and do not include volatile FX refresh timestamps.
- A changed broker execution INR amount or revised historical FX observation changes calculated attributes and reproducibility fingerprints, but not Purchase/Sale ID unless a frozen defining attribute changes.
- If actual canonical purchase price is denominated in INR, document that clearly and preserve the local price as a separate nonidentity attribute; do not mix currencies in one Price column without an explicit unit.

### Done when
IDs remain stable for unchanged economic defining attributes while FX-dependent financial outputs can be replayed and explained.

## 11. Logical immutability under full rebuild

Silver/Gold may be physically replaced.

Logical immutability means:

```text
same reproducible evidence
+ same rules/reference state
+ same implementation contract
→ same deterministic ID
+ same material attributes
```

It does **not** require append-only Silver storage.

---

## 12. Consistent reconstruction across US market and Quant FIFO

### Change
The US historical market transformer reconstructs a holding spine, while the Quant Engine independently reconstructs tax/analytics lots.

### Impact
Two independently ordered same-day purchases or sales can produce different holdings/basis even with identical input data.

### Implementation
- Reuse the frozen canonical same-day purchase/sale ordering in both consumers, using a shared ordering helper or shared canonical ordered input.
- Preserve the existing market table's aggregate grain; do not add transaction IDs to market snapshots.
- Add a cross-engine checkpoint at common ISIN/date points for total quantity and comparable cost-basis measures, with documented differences where the engines use different definitions.
- Keep realized-tax ownership exclusively in the main Quant FIFO, not the market-history spine.

### Done when
Both reconstruction paths agree on the financial state they are intended to share, independently of input row order.

## 13. FIRE / Monte Carlo reproducibility

Persist:

```text
simulation_id
run_id
created_at
root_seed
iterations
horizon
input_as_of_date
settings_snapshot_id
rules_snapshot_id
input_fingerprint
model_fingerprint
model_implementation_version
status
result_fingerprint  # optional
```

Persist one root seed. Derive deterministic stochastic streams. Do not persist every random draw.

---

## 14. Fingerprint scope

```text
input_fingerprint
→ canonical financial inputs

model_fingerprint
→ assumptions + configuration + behavior-controlling parameters

model_implementation_version
→ algorithm/model implementation compatibility boundary

root_seed
→ stochastic context
```

Exclude volatile execution metadata.

---

## 15. Simulation persistence

Historical authority:

```text
cp_simulation_runs
```

Latest DuckDB projection:

```text
meta.m_Simulation_Run
```

Preserve:

```text
SQLite → historical authority
DuckDB Meta → latest analytical projection
```

---

## 16. Contract Registry fingerprint

The Data Contract Registry is the inventory SSOT.

Create deterministic:

```text
Contract_Registry_Fingerprint
```

from canonical, deterministically sorted contract definitions including material contract attributes such as:

```text
contract_id
layer
physical table
grain
producer
publication order
schema/contract definition where available
```

Persist the fingerprint with run/reproducibility metadata.

Do **not** maintain a manual registry version counter.

Exact Bronze/Silver/Gold counts always come from the registry.

---

## 17. Reproducibility Envelope

Important outputs are explainable by:

```text
source evidence
run identity
Settings snapshot
FinancialRules / TaxConfig snapshot
Macro FY parameters
Contract Registry fingerprint
model/algorithm implementation
root seed where stochastic
```

Investment/tax lineage:

```text
canonical purchase / sale
→ Lot_ID
→ Realized_Event_ID
→ Tax_Event_ID
→ FY Tax State
→ Gold
```

Deterministic invariant:

```text
same evidence + settings + rules + macro + registry + implementation
→ same material output
```

Stochastic invariant adds the same root seed.

---

## 18. Simulation replay numerical contract

Within the supported `model_implementation_version` boundary:

```text
discrete outputs → exact equality
floating scalars → approved abs_tol + rel_tol
floating arrays/distributions → element-wise approved abs_tol + rel_tol
```

Keep tolerance constants centralized.

Relevant runtime/library versions may be emitted in replay-test diagnostics.

---

## Goal

Extend the current architecture with:

```text
Artifact ↔ Run lineage
Deterministic analytical identity
FIRE / Monte Carlo replayability
Contract Registry fingerprinting
One Reproducibility Envelope
```

Do not redesign the Control Plane, Bronze/Silver/Gold architecture, recovery model, or orchestration.

---

## Out of scope

```text
new orchestration framework
new warehouse layer
event-sourcing rewrite
distributed transactions
generic lineage platform
separate tax-lineage platform
source-row broker transaction redesign
random analytical UUIDs
manual registry version counter
persistence of every Monte Carlo draw
```

---


---

## Architecture Implementation Freeze checklist

1. Artifact lifecycle pointers.
2. Artifact-run event history with reason.
3. Rename remains identity migration.
4. Native identity precedence.
5. Canonical ID Serialization v1.
6. Identity/provenance separation.
7. Existing canonical investment grain preserved.
8. Logical immutability compatible with full rebuild.
9. FIRE seed/fingerprints/implementation version persisted.
10. Historical simulation provenance in SQLite.
11. Latest simulation context in Meta.
12. Contract Registry fingerprint.
13. Finance/tax stable lineage IDs.
14. One Reproducibility Envelope.
15. One replay numerical tolerance contract.
