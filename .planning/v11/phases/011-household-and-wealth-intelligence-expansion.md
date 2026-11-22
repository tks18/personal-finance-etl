# Phase 011 - Household and Wealth Intelligence Expansion

**Target release:** v11.3.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 010  
**Next:** Phase 012  
**Risk:** Medium-High

## 1. Outcome

Add the three approved household/wealth analytics using existing financial truth without expanding Silver topology.

## 2. Why this phase exists

- With naming migration complete, new methodology can be regression-isolated from schema cleanup.
- The approved analytics answer personally useful questions rather than adding generic metric inventory.

## 3. Inherited repository state

- Phase 010 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- existing monthly financial/wealth/cashflow Gold surfaces
- wealth engine monthly ledger/net-worth state
- income/expense classifications and financial-year parameters
- cleaned Silver/Gold vocabulary from v11.2.0

## 5. Exact target state after this phase

Add the three approved household/wealth analytics using existing financial truth without expanding Silver topology.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Implement net-worth change attribution with an explicit reconciliation identity and visible residual; never hide an unexplained difference

Implement net-worth change attribution with an explicit reconciliation identity and visible residual; never hide an unexplained difference.

### Step 2 - Implement lifestyle/real-expense growth using the configured inflation assumption, clearly labeling it as PFETL-assumption-adjusted rather than official CPI unless actual CPI evidence exists

Implement lifestyle/real-expense growth using the configured inflation assumption, clearly labeling it as PFETL-assumption-adjusted rather than official CPI unless actual CPI evidence exists.

### Step 3 - Implement income resilience metrics: passive-income share, passive-income/core-expense coverage and active-income dependency

Implement income resilience metrics: passive-income share, passive-income/core-expense coverage and active-income dependency.

### Step 4 - Place each metric into an existing Gold table when grain matches; create a new Gold surface only if a distinct grain is unavoidable

Place each metric into an existing Gold table when grain matches; create a new Gold surface only if a distinct grain is unavoidable.

### Step 5 - Add formula-level unit tests and real-data trend sanity checks

Add formula-level unit tests and real-data trend sanity checks.

### Step 6 - Update retained Markdown methodology docs only for the new approved calculations

Update retained Markdown methodology docs only for the new approved calculations.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- New household/wealth methodology is additive and separately regression-tested.

## 9. Tests and verification

- [ ] Net-worth attribution reconciles to change in net worth or exposes an explicit residual.
- [ ] Inflation-adjusted expense growth uses the configured assumption and is clearly labeled.
- [ ] Income resilience metrics reproduce independently calculated test fixtures.
- [ ] No Silver table/column is added unless an approved analytic demonstrably requires it.
- [ ] Existing Gold values remain unchanged outside the new fields/surface.

## 10. Explicit non-goals

- Do not implement expense volatility, arbitrary trend analytics, AI interpretation or rebalancing recommendations.

## 11. Completion checklist

- [ ] Exit assertion: Net-worth attribution reconciles to change in net worth or exposes an explicit residual.
- [ ] Exit assertion: Inflation-adjusted expense growth uses the configured assumption and is clearly labeled.
- [ ] Exit assertion: Income resilience metrics reproduce independently calculated test fixtures.
- [ ] Exit assertion: No Silver table/column is added unless an approved analytic demonstrably requires it.
- [ ] Exit assertion: Existing Gold values remain unchanged outside the new fields/surface.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 012

The next phase may assume only the verified state above. It begins **Investment and Tax Intelligence Expansion** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 011
Target release: v11.3.0
Files changed:
Contracts/schema changed:
Financial formulas changed:
Protected identity comparison:
Focused tests:
Architecture tests:
Real-data verification:
Power BI verification:
Observability/recovery verification:
Compatibility/transitional state remaining:
Semantic commit groups:
Exit assertions green: yes/no
```
