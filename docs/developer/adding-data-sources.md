# Adding a Data Source

A new data source should enter the platform without teaching every downstream engine about its original shape.

The target lifecycle is:

```mermaid
flowchart LR
    SRC["New Source"] --> DISC["Discovery"]
    DISC --> CP["Control Plane"]
    CP --> EXT["Extractor"]
    EXT --> BR["Bronze"]
    BR --> CAN["Canonical Contract"]
    CAN --> ENG["Existing Engines"]
```

The key design question is:

> **Where does source-specific behaviour stop?**

The answer should usually be: **before canonical finance begins.**

---

## 1. Decide what kind of source this is

Before writing code, classify the source.

### Historical/event source

Examples:

```text
daily broker snapshot
transaction export
historical market file
```

Typical Bronze behaviour:

```text
file-aware replacement
```

### Current/reference source

Examples:

```text
mapping
master
opening-state reference
```

Typical Bronze behaviour:

```text
full replacement
```

Do not choose append/upsert mechanics before understanding source semantics.

---

## 2. Give the source a discovery category

The orchestrator builds a categorized source map.

Some sources come from folder discovery:

```python
discovered_files = categorize_statement_files(
    self.cfg.STATEMENTS_FOLDER,
    strict=True,
)
```

Others are explicit configured inputs:

```python
discovered_files["opening_balances"] = [
    self.cfg.OPENING_BALANCE_CSV_PATH
]
```

A new source needs a stable category because that category participates in:

- file-type policy,
- Control Plane registration,
- Bronze mapping,
- full-replace policy,
- extraction routing.

Choose the category as a semantic identifier, not a display label.

---

## 3. Add file-type/hash policy where required

`FileSyncService` maps categories to physical types:

```python
file_type = FILE_TYPE_MAP.get(
    category,
    "csv",
)

should_check_hash = getattr(
    hash_policy,
    file_type,
    False,
)
```

If the new source introduces a new physical type, make sure the hash policy understands it.

The question is:

> **For an already-known path, should content identity be rechecked?**

That is an ingestion policy decision.

---

## 4. Let the Control Plane own artifact identity

Do not create a second source registry.

The existing lifecycle already handles:

```text
relative path
file category
physical type
SHA-256
size
payload bytes
sync status
first / last ingestion
```

New/changed artifacts should flow through `ArtifactRepository` and `FileSyncService`.

That keeps:

```text
what exists?
what changed?
what bytes were ingested?
has it reached Bronze?
```

inside one authority.

---

## 5. Persist evidence before analytical processing

The Control Plane stores actionable source bytes.

Conceptually:

```python
with open(filepath, "rb") as file:
    raw_bytes = file.read()

# registry + payload persistence happens in the
# Control Plane before Bronze synchronization
```

Do not bypass raw persistence for convenience unless the source genuinely cannot be represented as an artifact.

External/API data can use virtual artifacts instead.

---

## 6. For API/provider data, use virtual artifacts

The current benchmark lifecycle demonstrates the pattern.

Virtual identity uses:

```text
virtual://<category>/<filename>
```

The artifact still receives:

```text
deterministic identity
content hash
payload
sync status
```

So external acquisition does not become provenance-free data merely because it was not discovered in a local folder.

---

## 7. Implement extraction at the source boundary

The extractor should convert persisted source evidence into a source-shaped analytical frame.

Its job is not to calculate household net worth or XIRR.

Keep the responsibility narrow:

```text
bytes / file
      ↓
parse
      ↓
source-shaped typed frame
```

Source-specific cleanup belongs here when it is truly about physical/source representation.

Financial meaning belongs later.

---

## 8. Register Bronze persistence

The new extracted dataset needs a Bronze destination.

Conceptually:

```text
source category
      ↓
Bronze table mapping
      ↓
persistence behaviour
```

For historical sources, preserve source identity such as:

```text
__file_name__
```

so changed artifacts can replace only their own Bronze partition.

---

## 9. Choose replacement semantics deliberately

### Historical

Conceptually:

```text
changed source file
      ↓
DELETE Bronze rows owned by that source
      ↓
INSERT replacement rows
```

### Full replacement

Conceptually:

```text
DELETE current reference state
      ↓
INSERT complete replacement
```

The decision should be based on what the source represents.

Not on which SQL statement is easiest.

---

## 10. Mark the artifact synced only after Bronze succeeds

The lifecycle is:

```text
Raw persisted
→ PENDING_BRONZE
→ extraction
→ Bronze write
→ SYNCED
```

Do not mark the source synchronized before analytical persistence completes.

That state transition is what makes interrupted ingestion recoverable.

---

## 11. Add the source to complete Bronze reconstruction

After actionable synchronization, the pipeline reads complete Bronze state.

The source must become part of the returned `ExtractionResult` or equivalent canonical input surface.

Conceptually:

```python
return ExtractionResult(
    existing_source_a=_get_lf(...),
    existing_source_b=_get_lf(...),
    new_source=_get_lf("bronze.r_New_Source"),
)
```

The exact field should represent the source's role clearly.

---

## 12. Transform into canonical finance

This is the most important step.

Do not expose:

```text
ProviderColumnA
ProviderColumnB
SheetName
VendorStatus
```

to downstream financial engines.

Map them into stable concepts.

For example:

```text
vendor transaction code
        ↓
canonical purchase / sale

vendor account label
        ↓
canonical asset identity
```

The canonical contract is the anti-corruption layer.

---

## 13. Use mapping/reference configuration where values vary

If the source uses different labels for an existing financial concept, prefer mapping/configuration.

If the source requires fundamentally different parsing or behaviour, use an adapter/extractor boundary.

Decision test:

```text
same behaviour, different value
→ mapping/configuration

different parsing / behaviour
→ adapter/extractor
```

Avoid giant source-specific conditional blocks in the transformation DAG.

---

## 14. Preserve grain

Write the source grain before implementing transformations.

Examples:

```text
one row per bank transaction
one row per broker order
one row per ISIN-date market observation
one row per month-account balance
```

Then write the target canonical grain.

If the transformation changes grain, document exactly how and why.

---

## 15. Define data-quality checks

Ask what must be true for the source to be financially usable.

Examples:

```text
transaction date present
amount parseable
instrument identity present
currency valid
duplicate identity understood
tax classification available downstream
```

A parser that returns rows is not necessarily a valid financial ingestion path.

---

## 16. Decide failure semantics

Should one malformed file:

```text
fail the run?
be skipped with explicit failure state?
quarantine the artifact?
```

The current production system generally prefers explicit failure over silently incomplete financial state.

Do not add `except Exception: pass` around source errors.

---

## 17. Update operational configuration

If the source introduces:

- a new path,
- a new file category,
- a new hash policy,
- a new source toggle,

update the operational Settings model.

Do not place source locations in FinancialRules.

Remember:

```text
Settings
→ operational environment

FinancialRules
→ financial semantics
```

---

## 18. Update the Data Contract Registry only if persistence contracts change

Adding a source does **not** automatically require a new Silver/Gold contract.

If the source feeds an existing canonical contract:

```text
new source
→ existing canonical finance
→ existing Silver/Gold
```

that is ideal.

Create a new persistent analytical contract only when the downstream financial object is genuinely new.

---

## 19. Reconcile downstream outputs

A new source can change financial truth intentionally.

Validation should therefore answer:

```text
What new evidence entered?
Which canonical state changed?
Which household/investment totals changed?
Can the change be explained from the source?
```

If the source is merely an alternative provider for the same evidence, stronger equivalence may be expected.

---

## 20. Update documentation

At minimum inspect:

```text
getting-started/configuration.md
architecture/data-lifecycle.md
architecture/data-model.md
developer/adding-data-sources.md
reference contracts
manifest.json if a new guide was added
```

Use real implementation excerpts once the source path is stable.

---

## 21. Source-extension checklist

- [ ] Source semantics classified
- [ ] Discovery category added
- [ ] Physical type/hash policy handled
- [ ] Control Plane lifecycle reused
- [ ] Raw payload persisted
- [ ] Extractor implemented
- [ ] Bronze destination defined
- [ ] Replacement semantics defined
- [ ] Source identity preserved where historical
- [ ] `PENDING_BRONZE → SYNCED` lifecycle respected
- [ ] Complete Bronze reconstruction updated
- [ ] Canonical mapping implemented
- [ ] Grain documented
- [ ] Data-quality checks defined
- [ ] Failure semantics explicit
- [ ] Settings updated if required
- [ ] FinancialRules changed only for financial policy
- [ ] Downstream financial outputs reconciled
- [ ] Docs updated

---

## Example extension shape

```text
New Broker
   │
   ├── discovery category
   ├── hash / artifact lifecycle
   ├── broker extractor
   ├── Bronze source table
   └── canonical mapping
            ↓
     Existing Purchase / Sale / Market contracts
            ↓
     Existing FIFO / Tax / Benchmark engine
```

That is the architecture working correctly.

[← Developer Home](README.md) · [← Documentation Home](../README.md)
