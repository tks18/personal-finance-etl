# Phase 057 - External Investment Topology Certification and Column Retirement

**Target release:** v10.5.3  
**Expected effort:** 5-7 hours  
**Previous:** Phase 056  
**Next:** Phase 058  
**Risk:** Critical

## 1. Outcome

Certify the completed canonical architecture against external domestic and foreign investment topologies, then perform the final consumer-backed investment/reference/provider Bronze/Silver column-retirement archaeology before performance hardening and contract freeze.

The phase must prove that different broker/source layouts converge into the same canonical investment evidence and that downstream PURCHASE, SALE, LOT, REALIZED, RECON and TAX identities remain stable because financial truth no longer depends on vendor vocabulary.

## 2. Why this phase exists

Investment certification is the strongest test of source-semantic independence. External evidence may differ in:

- buy/sell action vocabulary;
- transaction/holding split;
- broker count;
- instrument identifiers;
- domestic/foreign classification;
- provider symbol mapping;
- currency/FX requirements;
- benchmark assignment.

Those differences must terminate before canonical Bronze. FIFO, reconciliation, Tax, performance, Wealth and FIRE must receive the same PFETL-owned meaning.

This is also the final chance to remove source/provider residue from investment/reference/provider contracts before Phase 059 freezes the contract universe.

## 3. Inherited repository state

Phase 056 guarantees:

- the canonical source-binding/route/production architecture is externally proven for household N:M topologies;
- household Bronze/Silver column dispositions are closed;
- replay/recovery works with route/producer changes;
- Shan household outputs remain equivalent;
- no household vendor-shaped compatibility path remains.

Phase 055 additionally guarantees that investment Silver already consumes canonical evidence and the protected identity chain is unchanged.

## 4. Current codebase anchors

Use the post-055 equivalents of:

- investment SourceBinding/route/production configuration and planner code;
- `contracts/datasets.py`, `market.py`, `capabilities.py`, provenance and canonical field contracts;
- investment Silver preparation/transforms;
- FIFO/lot, realized, reconciliation and Tax domains;
- benchmark/FX/foreign-asset enrichment;
- provider-generated market evidence planning;
- `infrastructure/warehouse/{bronze,silver,gold,contracts}.py`;
- provider clients/caches only through existing provider abstractions;
- diagnostics, replay and observability services.

Fixtures must use deterministic static provider responses/cache evidence. Do not depend on live market services for certification.

## 5. Exact target state after this phase

### Domestic external topology

A source layout unrelated to Shan can provide canonical:

- `INVESTMENT_TRANSACTIONS`;
- `INVESTMENT_HOLDINGS`;
- `INVESTMENT_INSTRUMENTS`;
- required domestic reference/price evidence.

No foreign/FX provider work occurs when not required by the ExecutionPlan.

### Foreign external topology

A different topology can provide foreign investment evidence and cause the plan to request exactly the required:

- `FX_RATES`;
- `INSTRUMENT_PRICES`;
- benchmark evidence where enabled;
- provider symbol mapping.

US-specific source architecture must not be required; geography is data/capability context.

### Multi-broker convergence

Two or more broker bindings with different action vocabularies can converge through semantic mapping and explicit union into one canonical transaction dataset without duplicate or order-dependent identity behavior.

### Holdings/transactions independence

Support the configured production paths actually allowed by the final contracts, including separate holdings and transaction bindings. Do not infer unsupported synthetic evidence merely to make a fixture pass.

### Investment/reference/provider column-retirement result

Every canonical Bronze and Silver field in the investment/reference/provider surface has an explicit KEEP/RENAME/MOVE/DERIVE/DELETE disposition based on real consumers and financial invariants.

Provider symbols and vendor columns remain only where they are genuinely canonical reference/provenance data; they do not leak into financial identity or source-independent Silver semantics.

## 6. Detailed implementation sequence

### Step 1 - Define the external investment scenario ledger

Create domestic, foreign and multi-broker scenarios with expected canonical transactions/holdings/instruments and expected downstream financial outcomes. Record protected ID-driving fields explicitly.

### Step 2 - Build domestic static evidence

Use novel column names, action encodings and broker identifiers. Include enough purchases/sales/holdings to exercise FIFO and realized events. Configure only the capabilities needed for domestic accounting/valuation.

### Step 3 - Prove domestic plan minimality

Assert the satisfiability and provider plans do not request foreign FX/foreign price work when no active evidence/capability requires it.

### Step 4 - Build foreign static evidence

Use a different source shape and canonical mapping. Provide deterministic FX/price/provider-symbol evidence through the supported provider path or static provider fixture.

### Step 5 - Prove foreign producer resolution

Verify exact canonical dependencies, provider requests and date/instrument scopes. Provider fallback/selection semantics remain distinct from canonical `UNION`.

### Step 6 - Multi-broker convergence

Map broker-specific actions such as `BUY`, `SELL`, `PURCHASE`, `REDEEM` or other fixture vocabulary into PFETL canonical action enums before Bronze. Explicitly union canonical fragments and validate post-assembly identity collisions.

### Step 7 - Protected identity certification

For equivalent canonical financial scenarios, compare the complete protected sets:

- PURCHASE;
- SALE;
- LOT;
- REALIZED;
- RECON_LOT_GROUP;
- RECON_GROUP;
- RECON_EVENT;
- TAX.

Reordering source rows/files or changing broker vocabulary must not alter IDs when canonical evidence is unchanged.

### Step 8 - Financial value certification

Compare quantities, cost basis, proceeds, realized gains, reconciliation balances, Tax values, benchmark/FX enrichments and relevant Gold outputs. Differences require root-cause proof; fixture convenience is never justification for methodology changes.

### Step 9 - Capability/preflight failure matrix

Certify early actionable failures for cases such as:

- foreign valuation requested without satisfiable FX evidence;
- missing instrument/provider mapping required by an active enrichment;
- Tax requested without mandatory accounting inputs;
- ambiguous canonical producer selection;
- missing canonical investment transaction producer.

No financial engine should start before the plan is satisfiable.

### Step 10 - Investment Bronze/reference/provider column archaeology

Trace every final canonical investment/reference/provider Bronze column to:

- financial evidence requirement;
- canonical identity/grain;
- provider/reference requirement;
- provenance;
- downstream consumer.

Retire historical fields such as vendor order-status strings, placeholder markers, display-only source labels or US-specific architecture fields when no canonical invariant requires them.

### Step 11 - Investment Silver column archaeology

Trace every investment Silver column across FIFO, reconciliation, Tax, performance, Wealth/FIRE and Gold. Preserve intentional advanced analytical contracts even if not used by one Gold mart. Remove dead/source-derived duplication only with evidence.

### Step 12 - Apply safe retirement and parity tests

Update contracts, schema adapters, transforms and tests together. Add contract/physical parity assertions for every changed dataset.

### Step 13 - Replay/recovery and provider lineage

Change one broker mapping and one provider/reference input. Verify dependency closure, replay, atomic failure behavior and observability lineage through provider request -> canonical evidence -> financial outputs.

### Step 14 - Full Shan regression

Run the accepted Shan investment configuration and compare protected IDs and financial outputs after all retirements.

## 7. Files and symbols in scope

Expected work:

- `tests/fixtures/evidence/` external investment/reference/provider fixtures;
- deterministic provider test responses/caches;
- investment/reference/provider DatasetContracts and schema adapters;
- investment Silver transforms and analytical contracts where retirement is proven;
- capability/preflight certification tests;
- protected ID/value comparison harness;
- architecture guards against vendor/provider leakage.

## 8. Cross-cutting impacts

**Financial correctness:** protected IDs and values are the primary oracle.

**Provider architecture:** provider-specific transport/symbol concerns remain at provider/reference boundaries; canonical market evidence stays provider-neutral.

**Capability planning:** domestic, foreign, benchmark, Tax and Wealth/FIRE requirements must remain composable.

**Replay:** binding/route/provider changes affect only their canonical dependency closure.

**Warehouse:** approved column retirements must update both base/effective contract and physical state.

**Observability:** provider request, SourceBindingId, canonical DatasetId and protected financial lineage remain reconstructable.

## 9. Tests and verification

Mandatory:

- external domestic topology with zero unnecessary foreign provider work;
- external foreign topology with exact FX/price/provider requirements;
- multi-broker union with different source action vocabularies;
- stable protected IDs across source reorder and equivalent source vocabularies;
- FIFO/realized/reconciliation/Tax value equivalence;
- capability/preflight failure matrix;
- duplicate canonical identity/conflict behavior;
- provider/reference replay and rollback;
- investment/reference/provider column disposition ledger complete;
- physical warehouse parity after retirements;
- full Shan investment/Tax/Gold regression green.

## 10. Explicit non-goals

Do not:

- add new brokers/providers solely for certification;
- change FIFO, reconciliation, Tax or performance methodology;
- create source-specific canonical DatasetIds;
- turn provider failover into generic union semantics;
- optimize runtime beyond fixing a certification-blocking regression;
- freeze the public contract universe before Phase 059.

## 11. Completion checklist

- [ ] Domestic, foreign and multi-broker external topologies reach canonical investment evidence without source-code changes.
- [ ] Provider and capability planning request only evidence required by the active canonical plan.
- [ ] PURCHASE, SALE, LOT, REALIZED, RECON_LOT_GROUP, RECON_GROUP, RECON_EVENT and TAX identities remain exact across equivalent external representations.
- [ ] FIFO, realized, reconciliation, Tax, FX, benchmark and valuation values remain financially equivalent.
- [ ] Every investment/reference/provider Bronze column has a consumer/invariant-backed disposition and approved retirements are applied.
- [ ] Every investment Silver column has an explicit contract disposition, preserving intentional advanced analytics while removing dead/source-specific residue.
- [ ] Replay/recovery and provider lineage remain correct after broker mapping/reference changes.
- [ ] Shan's complete investment/Tax/Gold regression remains green after the final retirement pass.

## 12. Commit boundary

Use `pfetl-conventional-commits`. Keep external certification, provider/reference contract retirement and Silver retirement in semantic groups that remain green and reviewable. Let the skill own exact staging/message mechanics.

## 13. Handoff to Phase 058

Phase 058 may assume household and investment external topology correctness is proven, all supported source-semantic/topology variations converge through the canonical architecture, and the final pre-freeze Bronze/Silver surfaces have completed consumer-backed retirement. Performance work may therefore optimize only the architecture that will actually be frozen in Phase 059.

## Phase completion record

```text
Phase:
Target release:
External scenarios certified:
Protected ID comparison:
Column ledgers closed:
Files changed:
Schema changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Shan regression:
Provider/replay verification:
Observability verification:
Compatibility path remaining: NONE
Exit assertions green:
Commits:
```

A phase is incomplete if any required exit assertion is false.
