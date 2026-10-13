# Personal Finance ETL — Finance Bugs

> **Purpose:** definitive finance-correctness backlog. Fix these before adding finance features.
>
> Each item gives the failure, the concrete fix, where it belongs, and the condition for calling it resolved.

---

## FIN-BUG-01 — Malformed populated broker numerics can become zero

**Priority:** P1 · **Risk:** High

### Problem

Some investment-source fields use permissive numeric casts followed by null/zero handling. That can collapse two very different states:

```text
blank source value       → optional missing value
"1O0" / malformed value  → parse failure → null → 0.0
```

A bad populated quantity, price, acquisition value, market value, or P&L must never become a valid zero.

### Resolve it

Create one reusable strict financial-number parser and use it across broker/investment adapters.

```text
raw value
  ├─ blank + optional field → null
  ├─ valid numeric          → parsed numeric
  └─ populated + invalid    → FinancialSourceValidationError
```

The error should carry:

- artifact/source;
- sheet/table where relevant;
- field name;
- raw value;
- row identifier/index where practical.

Do **not** solve this by making every field non-nullable. Missing and malformed are different states.

### Apply first to

- observed quantities;
- prices;
- acquisition/cost values;
- market values;
- realized/unrealized P&L inputs.

Then reuse the same parser for other financially material source numerics.

### Done when

A deliberately malformed populated broker numeric fails ingestion with source context, while a genuinely blank optional field still follows its documented null/default policy.

---

## FIN-BUG-02 — CPI computation failure can masquerade as `100.0`

**Priority:** P1 · **Risk:** High

### Problem

Inflation logic can catch an unexpected exception while deriving the latest CPI and substitute `100.0`.

That makes these states indistinguishable:

```text
valid documented base/default
unexpected computation failure
```

Because `100.0` is financially plausible, downstream wealth/FIRE logic can continue with bad state.

### Resolve it

Replace the broad fallback with explicit result semantics:

```text
VALID
NO_OBSERVATION
INVALID_INPUT
COMPUTATION_ERROR
```

Recommended flow:

```text
CPI series available?
  ├─ yes → calculate latest CPI → VALID
  └─ no  → NO_OBSERVATION

unexpected exception
  → COM​​PUTATION_ERROR / fail dependent calculation
```

Only use `100.0` if there is a **documented financial rule** that explicitly defines that value for a known state. Never use it as an exception fallback.

### Affected areas

- inflation builder;
- wealth/planning consumers of CPI;
- FIRE inputs derived from inflation state.

### Done when

Forced CPI calculation failure cannot produce a normal `100.0` value and downstream consumers can distinguish missing CPI from broken CPI computation.

---

## FIN-BUG-03 — Dynamic market extraction can publish incomplete required evidence

**Priority:** P1 · **Risk:** High

### Problem

FX, benchmark, and US-market extraction uses concurrent workers. Individual worker failures can be logged while successful frames remain available.

That permits:

```text
requested 8
successful 6
failed 2
      ↓
6 successful frames survive
```

For required market evidence, “some data arrived” is not the same as “the extraction is complete.”

### Resolve it

Introduce a structured batch result shared by dynamic extractors:

```text
requested_entities
successful_entities
cached_entities
no_new_data_entities
failed_entities
frames
```

Then give every extractor an explicit completeness policy.

Example:

```text
required entity failed
    → batch FAILED

provider returned valid no-new-data
    → allowed

cache fully covers requested period
    → allowed

optional entity failed
    → PARTIAL only if contract explicitly permits it
```

Only inject a new virtual Bronze artifact after the batch policy passes.

### Affected areas

- currency extractor;
- benchmark extractor;
- US-market extractor;
- orchestration that interprets extractor outcomes.

### Done when

A failed required ticker/currency/benchmark prevents ordinary successful publication and the failure records entity + interval + provider context.

---

## FIN-BUG-04 — Populated malformed dates can silently become null

**Priority:** P1 · **Risk:** High where chronology defines finance

### Problem

Permissive date parsing can turn an invalid populated date into null.

That is dangerous because dates participate in:

- deterministic transaction identity;
- FIFO ordering;
- holding period;
- financial year;
- tax classification;
- valuation;
- historical price/FX causality.

### Resolve it

Use a shared financial-date parser:

```text
blank + optional
    → null

valid populated
    → parsed Date

invalid populated
    → FinancialSourceValidationError
```

Apply strict handling first to dates used for identity, ordering, Tax, and valuation. Optional descriptive dates can retain looser semantics only when explicitly documented.

### Done when

Malformed populated dates fail at the source/canonical boundary instead of disappearing into null and altering downstream chronology.

---

## FIN-BUG-05 — Undefined CAGR can appear as a valid 0%

**Priority:** P2 · **Risk:** Medium

### Problem

XIRR already preserves typed validity states. CAGR can still return `0.0` for invalid/undefined inputs such as:

```text
start <= 0
end <= 0
duration <= 0
```

`0%` is a real financial result. Undefined is not.

### Resolve it

Introduce a typed result matching the XIRR philosophy:

```text
CagrResult
  value: float | None
  status:
    VALID
    INVALID_START_VALUE
    INVALID_END_VALUE
    INVALID_DURATION
    NUMERIC_ERROR
  reason: str | None
```

Gold/presentation should expose null value + status for invalid CAGR rather than manufacturing zero.

### Done when

A genuine flat investment can report `0%`, while an undefined CAGR reports no value and an explicit reason.

---

## FIN-BUG-06 — Financial invalid-state semantics are inconsistent

**Priority:** P2 · **Risk:** Medium

### Problem

Across financial calculations, abnormal state can currently appear as some mixture of:

```text
0
null
NaN
empty frame
exception
fallback value
typed status
```

Each may be locally reasonable, but inconsistent semantics make downstream interpretation fragile.

### Resolve it

Adopt a small shared vocabulary:

```text
VALID
MISSING_INPUT
INVALID_INPUT
UNDEFINED
STALE_EVIDENCE
NON_CONVERGENT
COMPUTATION_ERROR
```

Do not force every calculation into one class. Instead:

1. identify financially meaningful calculations;
2. document their allowed invalid states;
3. expose status where null/zero would otherwise be ambiguous;
4. keep exceptions for states that should abort the financial path.

### Done when

Zero always means a valid zero, null has a documented meaning, and invalid/undefined/stale calculations can be distinguished without inspecting implementation details.

---

# Recommended fix order

```text
FIN-BUG-01 strict broker numerics
        ↓
FIN-BUG-02 CPI failure semantics
        ↓
FIN-BUG-03 extraction completeness
        ↓
FIN-BUG-04 strict financial dates
        ↓
FIN-BUG-05 typed CAGR
        ↓
FIN-BUG-06 common validity semantics
```

The common theme is simple:

> **Bad or incomplete evidence must fail visibly before it becomes plausible financial state.**
