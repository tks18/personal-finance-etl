# Phase 053 - Household Silver Cutover and Source-Assumption Demolition

**Target release:** v10.4.2  
**Expected effort:** 3-5 hours  
**Previous:** Phase 052  
**Next:** Phase 054  
**Risk:** Very High

## 1. Outcome

Make household Silver consume only canonical household Bronze semantics and remove MoneyManager/source-container interpretation from the household financial domain.

At phase end `HOUSEHOLD_CORE` requires the new canonical household DatasetIds, old household source-container Bronze contracts have no runtime consumers, and household Silver/Gold financial outcomes remain equivalent to the v10.3.0 oracle.

## 2. Why this phase exists

Phase 052 intentionally stopped before changing financial consumers. Keeping both paths indefinitely would create exactly the dual architecture the program is trying to eliminate. This phase converts household Silver from source interpretation to financial reconstruction and removes the obsolete path immediately after equivalence is proven.

## 3. Inherited repository state

Phase 052 guarantees:
- six new household canonical Bronze datasets are produced and validated;
- old household Bronze/Silver remains available for deterministic comparison;
- source-specific category/transaction semantics are already represented canonically before Bronze;
- financial outputs have not changed yet.

## 4. Current codebase anchors

Trace every household Silver producer and helper that reads:
- old `HOUSEHOLD_ZCATEGORY`, asset-group, currency, `HOUSEHOLD_INOUTCOME` and opening-balance contracts;
- `IS_DEL`, `TYPE`, `TRANSACTION_TYPE`, `Z_PK`, `ZUID`, `ZASSETUID` or other source-oriented IDs/flags;
- FinancialRules classifications such as core expense, active income, dividend/interest, ledger roles;
- household capability requirements and Silver contract producers;
- wealth/FIRE downstream consumers that depend on household facts.

## 5. Exact target state after this phase

Household Silver producers consume only:
- canonical category hierarchy and `CategoryKind`;
- canonical `HouseholdTransactionKind`;
- canonical asset/category/currency/opening-balance identifiers/fields;
- FinancialRules for PFETL-owned financial classifications.

Silver must no longer know what source values such as `TYPE=0`, `TRANSACTION_TYPE=3`, `IS_DEL` or CoreData column names mean.

`HOUSEHOLD_CORE` canonical requirements switch atomically to the new household DatasetIds.

After the switch and equivalence proof, remove retired household source-container DatasetIds/contracts/DDL/Gate-2 schemas and runtime compatibility routes that only existed for old household Bronze.

## 6. Detailed implementation sequence

### Step 1 - Freeze the household source-assumption ledger
Before editing, enumerate each source-specific predicate/column in household Silver and classify it `MOVE BEFORE BRONZE`, `KEEP AS FINANCE`, or `DELETE`. Use this ledger as the demolition checklist.

### Step 2 - Cut category dimensions
Rewrite income/expense category/subcategory producers to derive their four Silver dimensions from `HOUSEHOLD_CATEGORIES.category_kind` and hierarchy only.

### Step 3 - Cut household transaction facts
Rewrite income/expense/transfer fact producers to consume canonical `transaction_kind` and canonical relationships. Remove source transaction-code branches.

### Step 4 - Cut assets/currency/opening-balance consumers
Replace source-field fallbacks with canonical identifiers/fields. Any still-needed source metadata must be justified as canonical evidence or moved to provenance, not reintroduced ad hoc.

### Step 5 - Protect FinancialRules boundary
Verify `Is_Core_Expense`, active/passive income, dividend/interest and ledger classifications remain PFETL-owned downstream rules. Do not encode those outcomes into SourceConfiguration.

### Step 6 - Build old-vs-new financial equivalence harness
Compare household Silver tables and affected Gold/Wealth/FIRE outputs at their defined grains. Compare values after intentional schema-name changes using an explicit mapping, not row order.

### Step 7 - Switch `HOUSEHOLD_CORE`
Replace old source-container requirements with the six canonical household DatasetIds. Re-run satisfiability for household-only, wealth and FIRE plans.

### Step 8 - Delete old household runtime path
Remove old DatasetIds/contracts/Gate-2 schemas/DDL and transitional routes when zero-reference proof succeeds. No aliases that let new code silently depend on old names.

### Step 9 - Add architecture guards
Reject `IS_DEL`, source TYPE codes, source transaction codes and retired DatasetIds from household Silver/domain code.

### Step 10 - Replay/upgrade proof
Upgrade a v10.3.0-style state through the new household path and verify mapping/semantic changes replay the correct canonical dataset before Silver rebuild.

## 7. Files and symbols in scope

Expected changes:
- household Silver/domain transforms;
- household capability requirements;
- retired household DatasetIds/contracts/schemas;
- Shan compatibility production declarations;
- architecture tests and financial-equivalence fixtures;
- wealth/FIRE tests affected by household input contracts.

Do not touch investment Silver beyond shared generic helpers.

## 8. Cross-cutting impacts

**Finance:** source interpretation is removed, but financial methodology remains unchanged.

**Capabilities:** `HOUSEHOLD_CORE` becomes genuinely source-topology-independent.

**Schemas:** old household Bronze tables disappear after successful cutover; new canonical household Bronze is authoritative.

**Replay:** old household DatasetIds must not survive in affected-dataset calculations.

**Observability:** events/context use new canonical household DatasetIds; source binding remains provenance context only.

## 9. Tests and verification

Required:
- four category Silver outputs match old-path financial content;
- income/expense/transfer facts match old-path content at stable grain;
- assets/currency/opening-balance downstream state is equivalent;
- FinancialRules classifications are unchanged;
- household-only capability plan resolves solely through new canonical evidence;
- Wealth/FIRE household contribution remains equivalent;
- all old household DatasetIds have zero production consumers before deletion;
- architecture grep/test rejects retired source columns/codes in household Silver;
- upgrade/replay from old state converges to same result as clean new run;
- full Shan Gold household/wealth/FIRE outputs remain equivalent within existing accepted numeric tolerances.

## 10. Explicit non-goals

Do not:
- redesign household financial methodology;
- add new category/transaction types beyond current supported meaning;
- perform final external-user column cleanup beyond columns proven obsolete by this cutover;
- migrate investment/reference/provider canonical evidence.

## 11. Completion checklist

- [ ] Household Silver category and transaction producers consume canonical semantics only; no source discriminator/deletion logic remains.
- [ ] Asset/currency/opening-balance consumers use canonical identifiers and no source-field fallbacks remain without explicit contract justification.
- [ ] FinancialRules-derived household classifications are unchanged and remain outside source configuration.
- [ ] `HOUSEHOLD_CORE` requires only the new canonical household evidence and all household/wealth/FIRE plans remain satisfiable.
- [ ] Old and new household Silver/Gold comparison is green at defined grains and tolerances.
- [ ] Retired household source-container DatasetIds/contracts/schemas/routes are deleted after zero-reference proof.
- [ ] Architecture/replay/upgrade tests prevent the retired household source semantics from returning.

## 12. Commit boundary

Use `pfetl-conventional-commits` to separate semantically coherent Silver cutovers, capability switch, and legacy demolition when appropriate. Commit groups must each leave the repository understandable; the commit skill determines exact staging/messages.

## 13. Handoff to Phase 054

Phase 054 may assume household is fully canonical and the generic architecture is proven by a real domain. It now applies the same model to the more complex investment/reference/provider evidence universe while leaving the existing investment Silver path temporarily active as the protected identity/financial oracle.

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
Commits:
```

A phase is incomplete if any required exit assertion is false.
