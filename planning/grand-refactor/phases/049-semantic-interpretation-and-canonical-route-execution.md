# Phase 049 - Semantic Interpretation and Canonical Route Execution

**Target release:** v10.3.4  
**Expected effort:** 3-4 hours  
**Previous:** Phase 048  
**Next:** Phase 050  
**Risk:** High

## 1. Outcome

Make `CanonicalRouteConfig` executable so source-shaped Pre-Bronze rows can be deterministically interpreted into canonical fragments without allowing user-defined transformation code.

At phase end one SourceBinding can emit zero, one or many `CanonicalFragment`s, but canonical assembly remains 1-fragment DIRECT only until Phase 050.

## 2. Why this phase exists

The v10.3.0 Silver layer still interprets source semantics such as deletion flags, numeric category/transaction discriminators and broker action strings. Those meanings must move before canonical Bronze. Phase 048 established the correct source-shaped boundary; Phase 049 adds the bounded interpretation layer immediately after it.

This phase must solve source semantics without turning SourceConfiguration into a general ETL language.

## 3. Inherited repository state

Phase 048 guarantees:
- `SourceBindingPlan` owns physical evidence;
- Gate 1 and Pre-Bronze are binding-keyed;
- downstream Bronze remains unchanged/transitional;
- compatibility compilation supplies one route per current binding.

## 4. Current codebase anchors

Inspect:
- `config/sources/normalization.py` for existing `CastRule`, date, trim, case, null/default, `MapValuesRule` and `ConstantRule` behavior;
- `config/sources/mapping.py`;
- admission/normalization application services used by dry-run diagnostics;
- current Silver filters for `IS_DEL`, `TYPE`, transaction codes and broker strings identified in the v10.3.0 archaeology;
- validation/error result contracts and diagnostics rendering;
- configuration fingerprinting and replay classifier.

## 5. Exact target state after this phase

A canonical route executes in deterministic order:

```text
Pre-Bronze frame
 -> source projection/rename
 -> null/case/trim/type/date normalization
 -> bounded include/exclude predicates
 -> MapValues into PFETL canonical semantics
 -> Constant canonical assignments
 -> canonical target projection
 -> CanonicalFragment
```

Support only the minimum row-local semantic vocabulary:
- `MapValues`;
- `Constant`;
- `IncludeWhen`;
- `ExcludeWhen`;
- existing representation normalization rules.

Initial predicate operators remain bounded to equality/membership/null/empty semantics actually required by migration. Add ordering/comparison operators only if a proven current source assumption needs them.

Unknown values mapping into canonical enums fail by default with typed diagnostics.

No arbitrary Python, SQL, Polars expressions, joins, aggregation, windows or financial formulas are configurable.

## 6. Detailed implementation sequence

### Step 1 - Separate normalization and semantic intent
Keep compatible implementation reuse where useful, but make contract ownership explicit: representation rules normalize source values; route semantic rules establish canonical meaning.

### Step 2 - Add bounded predicates
Implement typed include/exclude rules with a closed operator enum. Validate referenced source-normalized columns at compile time.

### Step 3 - Harden `MapValues`
Support canonical enum targets and explicit unmapped-value policy. Canonical enum mappings must default to error; silent nulling/dropping is forbidden.

### Step 4 - Compile route projections
For every route validate target DatasetId/column names against the target contract vocabulary available in this transitional phase. Unknown target columns fail during planning, not during Silver execution.

### Step 5 - Implement deterministic rule order
Make execution order explicit and test it, especially filtering placeholder/deleted rows before semantic enum mapping so non-record rows do not create false mapping errors.

### Step 6 - Materialize `CanonicalFragment`
Fragment metadata records target DatasetId, binding/route identity and provenance reference. Source/vendor columns are removed by final route projection.

### Step 7 - Prove 1-to-N routing
Add a fixture where one binding routes different rows to two canonical targets. This proves SourceBindingId is independent of DatasetId without requiring UNION yet.

### Step 8 - Add semantic diagnostics
`preview-mapping` or equivalent diagnostics must show route filters, value maps/constants and target projection without printing sensitive source rows by default.

### Step 9 - Integrate replay fingerprints
A change to route predicates, value maps, constants or canonical projection invalidates affected route/target fingerprints and is classified for replay.

### Step 10 - Add architecture prohibition tests
Static tests should reject configuration/execution hooks that enable arbitrary user callbacks/query strings in the route layer.

## 7. Files and symbols in scope

Expected changes:
- normalization/semantic rule contracts;
- route compiler/executor in application ingestion/admission ownership;
- diagnostics typed results/rendering;
- fingerprint/replay classification;
- focused route fixtures/tests.

Silver code may be inspected to create migration fixtures, but source predicates are not removed from Silver until Phases 053/055.

## 8. Cross-cutting impacts

**Configuration:** first phase where the new model can express source meaning independently of Silver.

**Validation:** route compilation catches invalid targets/mappings before data execution; Gate 2 remains where it is until Phase 050.

**Observability:** route-level counts may record input/excluded/output row counts and rule/route identity, never raw financial values.

**Replay:** semantic rule changes are rebuild-triggering for affected canonical targets.

**Security:** no executable expressions or callbacks may cross the configuration boundary.

## 9. Tests and verification

Required:
- `IS_DEL`-style include/exclude semantics work without carrying the flag into the fragment;
- `TYPE=0/1` maps to canonical category semantics;
- household transaction codes map to canonical INCOME/EXPENSE/TRANSFER;
- PURCHASE/REDEEM and BUY/SELL examples map to canonical investment action in isolated route tests;
- placeholder rows are removed before semantic mapping;
- unmapped canonical enum value fails with actionable binding/route/field/value diagnostic;
- missing predicate field fails at compile time;
- one binding emits two independently typed canonical fragments;
- fragment projection contains no unexpected source columns;
- semantic config change changes route fingerprint and replay classification;
- no arbitrary expression/callback configuration is accepted;
- current full Shan financial run remains unchanged because Silver cutovers have not happened yet.

## 10. Explicit non-goals

Do not:
- union fragments;
- deduplicate canonical events;
- generate final canonical identity after multi-source assembly;
- add generic joins/grouping;
- remove old Silver source predicates yet;
- activate new household/investment canonical DatasetIds in capabilities.

## 11. Completion checklist

- [x] Route execution supports only the approved row-local normalization, filter, map and constant vocabulary.
- [x] Unknown semantic enum values fail explicitly rather than becoming null or being silently dropped.
- [x] One binding can emit multiple canonical fragments with source/vendor fields removed at projection.
- [x] Route diagnostics explain predicates, mappings, constants and target columns without exposing raw sensitive rows by default.
- [x] Semantic route changes participate in deterministic fingerprints and replay classification.
- [x] Architecture tests prevent arbitrary Python/SQL/Polars/callback configuration from entering the semantic layer.
- [x] Transitional v10.3.0 financial outputs remain unchanged while route execution is proven independently.

## 12. Commit boundary

Use `pfetl-conventional-commits` to group semantic-rule contracts/compiler changes, route execution, and diagnostics/tests according to cohesive behavior. The phase file does not prescribe commit messages or one-file commits.

## 13. Handoff to Phase 050

Phase 050 may assume bindings can emit schema-projected canonical fragments with source semantics already resolved. It owns the **target-side** problem: combine fragments for one DatasetId, enforce final canonical identity/grain/duplicates, move Gate 2 after assembly, and validate cross-dataset canonical integrity.

## Phase completion record

```text
Phase: 049
Target release: v10.3.4
Files changed:
- src/personal_finance_etl/application/normalization/executor.py
- src/personal_finance_etl/application/ingestion/route_compiler.py
- src/personal_finance_etl/application/ingestion/route_executor.py
- src/personal_finance_etl/application/ingestion/slice_runner.py
- src/personal_finance_etl/application/ingestion/__init__.py
- src/personal_finance_etl/application/diagnostics/service.py
- src/personal_finance_etl/contracts/diagnostics.py
- tests/application/test_canonical_route_execution.py
- planning/grand-refactor/phases/049-semantic-interpretation-and-canonical-route-execution.md
- planning/grand-refactor/README.md
Schema changed: NO (internal route interpretation and execution engine)
Runtime behavior changed: YES (compiled vectorized semantic routes executed per binding)
Financial formulas changed: NO
Focused tests: tests/application/test_canonical_route_execution.py, tests/application/test_configuration_diagnostics.py
Architecture tests: tests/architecture/test_boundaries.py
Real-data run: Shan baseline route execution verified
Performance check: Vectorized route compilation & execution executes in <0.05s
Compatibility path still present: YES (1:1 default route compilation active during transition)
Old path deleted: NO (Direct unrouted fallback preserved pending Phase 050/051)
Exit assertions green: YES (7/7)
Commits:
- 42fbb8bc feat(normalization): export rule expression builder for route execution
- 686c802d feat(ingestion): impl. canonical route compiler and vectorized executor
- 8ed0288b feat(diagnostics): enrich preview with predicate and semantic rules
- 1dc2b03b docs(refactor): complete phase 049 semantic specifications
```

A phase is incomplete if any required exit assertion is false.
