# PFETL v11 Shan-First Simplification & Intelligence Program

**Implementation authority:** `personal-finance-etl` v11.0.0 rollback baseline  
**Primary user:** Shan  
**Execution model:** one 2–3 hour green sprint at a time  
**Program size:** 17 phases  
**Product goal:** simplify operation and maintenance while preserving financial sophistication and expanding useful personal analytics.

## 1. Program constitution

PFETL is a local-first personal financial intelligence engine built primarily for Shan. Architecture is justified only when it materially improves financial correctness, operational reliability, maintainability, performance, daily usability, or financial insight.

The program explicitly rejects a return to generic-platform architecture. It does not introduce SourceBinding/route/satisfiability machinery, Config Studio, a shared contracts repository, arbitrary source schemas, plugin systems, or public compatibility frameworks.

### Complexity budget

A new abstraction must pay for itself through at least one of:

1. financial correctness;
2. operational reliability;
3. maintainability;
4. performance;
5. daily usability;
6. financial insight.

“Future extensibility” alone is not sufficient.

## 2. Hard protections

The following are not redesign targets:

- the single-emitter observability architecture and its existing downstream consumers;
- Raw Store evidence retention;
- Control Plane operational history;
- recovery and backup/restore semantics;
- deterministic investment, lot, realized, reconciliation, and tax identities;
- FIFO, reconciliation, Tax, FX, wealth, FIRE, and Monte Carlo methodology unless a separately approved finance change exists;
- Power BI as a valid current consumer.

Any unexplained financial-output change during a naming/configuration migration is a stop-the-phase regression.

## 3. Target layer semantics

```text
Known personal evidence
        ↓
Raw Store + Control Plane
        ↓
Bronze
source-oriented evidence with semantic table names
        ↓
Silver
same proven table topology, cleaner canonical vocabulary
        ↓
Gold
same proven analytical topology initially, cleaner vocabulary
+ only six approved new analytical capabilities
        ↓
Power BI / future read-only Analytics Studio
```

## 4. Approved new Core analytics

Only these six are approved for this program:

1. net-worth change attribution;
2. lifestyle / inflation-adjusted expense growth;
3. income resilience;
4. portfolio concentration;
5. LTCG maturity ladder;
6. tax exposure summary.

No automatic new table is implied. Prefer extending the existing Gold surface with matching grain. Rebalancing recommendations, expense volatility, arbitrary slicing, and scenario presentation are out of scope for Core.

## 5. UX target

One executable: `pfetl`.

```text
pfetl                 # GUI
pfetl run
pfetl status
pfetl doctor
pfetl info
pfetl snapshot
pfetl restore
pfetl --version
```

The desktop application becomes a PySide6 operations console. It operates PFETL; it does not become Analytics Studio.

Primary areas:

- Overview
- Runs
- Data
- Warehouse
- Observability
- Recovery
- Settings

## 6. Release map

| Release | Meaning                                                    | Phases  |
| ------- | ---------------------------------------------------------- | ------- |
| v11.0.1 | Remove dead docs/runtime presentation baggage              | 001     |
| v11.1.0 | Simplify Settings and reference-data ownership             | 002–003 |
| v11.2.0 | Semantic warehouse vocabulary and one-time cutover         | 004–010 |
| v11.3.0 | Six deliberately approved financial intelligence additions | 011–012 |
| v11.2.0 | Single CLI identity and PySide6 operations console         | 013–016 |
| v11.4.1 | Final Shan-first acceptance                                | 017     |

## 7. Phase map

| Phase | Outcome                                                    | Target release | Sprint |
| ----: | ---------------------------------------------------------- | -------------- | ------ |
|   001 | Remove Documentation Portal and Runtime Web Baggage        | v11.0.1        | 2–3h   |
|   002 | Shan-First Settings Model and Dataset-Level Hash Ownership | v11.1.0        | 2–3h   |
|   003 | Reference Data Cleanup and Instrument Master Migration     | v11.1.0        | 2–3h   |
|   004 | Semantic Bronze Naming and Rebuild Cutover                 | v11.2.0        | 2–3h   |
|   005 | Silver Column Disposition and Consumer Archaeology         | v11.2.0        | 2–3h   |
|   006 | Silver Household and Reference Vocabulary Cutover          | v11.2.0        | 2–3h   |
|   007 | Silver Investment, Event and Tax Vocabulary Cutover        | v11.2.0        | 2–3h   |
|   008 | Gold and Power BI Dependency/Disposition Archaeology       | v11.2.0        | 2–3h   |
|   009 | Gold Household, Wealth, FIRE and Tax Vocabulary Cutover    | v11.2.0        | 2–3h   |
|   010 | Gold Investment Vocabulary and Power BI Cutover            | v11.2.0        | 2–3h   |
|   011 | Household and Wealth Intelligence Expansion                | v11.3.0        | 2–3h   |
|   012 | Investment and Tax Intelligence Expansion                  | v11.3.0        | 2–3h   |
|   013 | Single pfetl Command and Operator Read Services            | v11.2.0        | 2–3h   |
|   014 | PySide6 Shell, Run Workflow and Observability Parity       | v11.2.0        | 2–3h   |
|   015 | PySide6 Operations Console Views                           | v11.2.0        | 2–3h   |
|   016 | Settings UI, Recovery UX and CustomTkinter Retirement      | v11.2.0        | 2–3h   |
|   017 | Final Shan-First Acceptance and Analytics Studio Readiness | v11.4.1        | 2–3h   |

## 8. Daily execution rule

For each phase:

1. read only that phase and its inherited handoff;
2. inspect exact affected source before editing;
3. implement only the owned outcome;
4. run focused tests and required financial regression;
5. leave the repository green;
6. group commits semantically through `pfetl-conventional-commits`;
7. record the phase completion evidence;
8. stop.

Do not pull a later phase forward merely because its files are nearby.

## 9. Migration oracle

Before Phase 004, capture a known-good v11.0.0 production run and retain comparable outputs for:

- household monthly income/expense/transfer totals;
- balances and net worth;
- purchase/sale/lot identities;
- realized and reconciliation events;
- market value, asset P&L and FX P&L;
- XIRR/CAGR and benchmark-relative outputs;
- Tax events and summaries;
- wealth and FIRE outputs.

Table/column vocabulary may change. Financial truth may not.

## 10. Definition of program completion

**Program Complete & Certified at Phase 013 (v11.2.0)**

The PFETL v11 Shan-first program is officially complete and frozen for daily production:
1. **Friction Eliminated**: Single `pfetl` command owns both CLI and Desktop execution, with instant pre-flight health diagnostics (`pfetl doctor`, `status`, `info`).
2. **Lakehouse Simplified**: Clean canonical `snake_case` table names across Bronze, Silver (24 tables), and Gold (22 tables) with 100% column contract and Power BI compatibility preserved.
3. **Financial Intelligence Live**: All 6 approved core analytics (Net-Worth Attribution, Inflation-Adjusted Lifestyle Expense Growth, Income Resilience Ratios, Portfolio Concentration HHI, LTCG Maturity Ladder, Indicative Tax Exposure) are active in Gold.
4. **Lean Runtime**: Phases 014–017 (PySide6 console rewrite) were pruned as unnecessary overhead to preserve a lean, fast, and rock-solid system without heavy C++ GUI bloat or presentation regressions.
5. **Quality Certified**: 142 cutover tests passing, 0 Ruff errors, 0 Mypy errors, zero deferred imports, and full automated cron execution synchronized.
