# Phase 034 - Provider-Generated Market Evidence Migration

**Target release:** v10.0.0-rc7  
**Expected effort:** 3-4 hours  
**Previous:** Phase 033  
**Next:** Phase 035  
**Risk:** High

## 1. Outcome

Generalize provider-generated market evidence (`currency_fx_raw`, benchmark history, US market history and any equivalent current streams) into the same DatasetId/contract/admission architecture without pretending these datasets are user-uploaded files.

At phase end all current Bronze evidence streams are represented by the generalized architecture.

## 2. Why this phase exists

Provider-generated evidence differs from file-backed evidence: its raw truth is provider request/response provenance rather than a user file selector. Forcing it into a fake CSV/Excel source would corrupt the source model. It needs a provider-aware DatasetPlan that still lands in Pre-Bronze/canonical Bronze and participates in validation/recovery.

## 3. Inherited repository state

Phase 033 guarantees all user/file-backed investment evidence generalized. Existing provider request provenance, caches and observability remain intact. Phase 012 already isolated provider-specific symbols from canonical finance.

## 4. Current codebase anchors

Historical streams:
- `currency_fx_raw`
- `benchmark_history_raw`
- `us_stock_market_data_raw`

Anchors:
- `application/ingestion/market_sync.py`
- market provider adapters/services
- provider request Control Plane table/repository
- market caches/artifacts
- current Bronze contracts
- Quant/valuation consumers.

Generate exact provider-stream table at phase start from registry.

## 5. Exact target state after this phase

Define provider-generated source planning explicitly.

Conceptually:
```text
ExecutionPlan requires enrichment
 -> ProviderDatasetPlan
 -> provider request parameters
 -> Control Plane provider-request provenance/cache
 -> response-shaped frame
 -> SOURCE/provider validation
 -> Pre-Bronze
 -> normalization
 -> BRONZE validation
 -> canonical Bronze
```

No fake filesystem location or file selector is required.

Provider request identity/provenance links the evidence to run, provider, DatasetId and request fingerprint.

Inactive capabilities do not request unnecessary provider evidence.

## 6. Detailed implementation sequence

### Step 1 - Define provider-generated dataset plan
Reuse SourceId/DatasetId concepts but use a typed provider/request selector rather than file selector. Keep this additive to source model; do not overload `ExcelSelector`.

### Step 2 - Integrate existing provider request provenance
Use current Control Plane provider-request table/cache. Do not create duplicate request history.

### Step 3 - Migrate currency FX
Validate response shape, persist Pre-Bronze, normalize/validate canonical Bronze, compare FX rates.

### Step 4 - Migrate benchmark history
Preserve benchmark series/date/value semantics and Quant inputs.

### Step 5 - Migrate US market history
Preserve market dates/prices/symbol mapping and valuation inputs.

### Step 6 - Capability-aware request proof
Use Phase-016/015 planner: when enrichment capability is inactive, provider request and dataset production are absent.

### Step 7 - Failure/cache/retry proof
Provider failure, cached response, retry/rate-limit behavior remain governed by existing provider infrastructure; validation failure does not publish canonical Bronze.

### Step 8 - Remove legacy provider-to-Bronze branches
All provider evidence now passes the same trust-boundary architecture.

## 7. Files and symbols in scope

Modify:
- provider dataset-plan contract;
- market sync/application orchestration;
- provider response validation/admission;
- Pre-Bronze/Bronze contracts;
- tests.

Do not redesign HTTP provider clients/retry algorithms.

## 8. Cross-cutting impacts

**Persistence:** provider response-shaped Pre-Bronze state.

**Provenance:** provider request ID/fingerprint replaces file artifact identity where appropriate; both are canonical evidence provenance variants.

**Identity:** time-series natural grain/uniqueness preferred; no unnecessary synthetic IDs.

**Observability:** preserve provider events and correlate DatasetId/source/request with run lineage.

**Performance:** caching must remain effective; generalized admission must not cause duplicate network calls.

## 9. Tests and verification

Required per provider dataset:
- cached and fresh response paths;
- source/provider validation;
- canonical Bronze equivalence;
- natural grain/uniqueness;
- provider failure and validation failure;
- inactive capability => zero provider call;
- request count/range equivalence;
- full valuation/Quant outputs identical;
- full Shan run.

## 10. Explicit non-goals

Do not:
- model provider data as fake user files;
- alter provider retry/rate-limit behavior;
- change FX/benchmark/valuation methodology;
- remove fixed discovery globally until Phase 035.

## 11. Completion checklist

- [ ] All provider-generated Bronze streams generalized.
- [ ] Provider request provenance reused.
- [ ] No fake file selector introduced.
- [ ] Cache/network behavior preserved.
- [ ] Capability-aware request skipping works.
- [ ] Canonical values unchanged.
- [ ] All 20 Bronze streams now have generalized representation.

## 12. Commit boundary

```text
feat(ingestion): generalize market-provider evidence
```

## 13. Handoff to Phase 035

Phase 035 may assume every current Bronze evidence stream has a production generalized route. It can finally delete the remaining global fixed discovery/injection/category topology rather than preserving compatibility for any dataset.

## Phase completion record

```text
Phase:
Target release:
Files changed:
Schema changed:
Runtime behavior changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Real-data run:
Performance check:
Compatibility path still present:
Old path deleted:
Exit assertions green:
Commit:
```

A phase is incomplete if any required exit assertion is false.
