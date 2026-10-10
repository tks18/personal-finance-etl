# Personal Finance ETL v8.1.0 | Production Hardening Plan

**Baseline:** v8.0.0. **Scope:** actual code correctness and robustness before documentation mode. **Status:** implementation plan, not a claim that fixes have been executed.

## Purpose
Close the concrete source-level issues found in the v8.0.0 archaeology, including the three `capital_gains_groups` problems. Keep the existing architecture and avoid feature expansion. Comprehensive QA suites, golden test development, and documentation rewriting remain separate.

## Priority and evidence
**P1** means potentially material financial misstatement or a direct frozen-contract violation. **P2** means correctness/robustness risk with narrower impact. **Conditional** means confirm the actual execution scenario before changing behavior. File references are investigation anchors from the earlier static review; line numbers may shift.

## Implementation batches

| Batch | Work | Issue IDs |
|---|---|---|
| 1 | Historical market and FX evidence | F01–F03 |
| 2 | Tax classification and calculations | CG01–CG03, F04–F07 |
| 3 | Tax Gold, credits and forecast | F08–F10 |
| 4 | Identity, source amounts and return presentation | F11–F14 |
| 5 | Snapshot consistency (conditional) | F15 |

## Issue-by-issue fixes

### F01 | P1 | US historical price backfill

**Where:** `backend/transform/us_stocks_transformer.py`.

**Problem:** Future price observations can populate earlier dates, and unavailable prices can become zero.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Keep prior-observation as-of prices; remove backward fill and zero fallback for missing market evidence. Retain missing status and effective observation date.

**Done when:** No pre-history price is fabricated.

### F02 | P1 | US market FX backfill

**Where:** `backend/transform/us_stocks_transformer.py`.

**Problem:** FX rates from later dates can be applied to earlier valuation dates.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Remove future-looking fill; allow same/prior observed rates only; fail or mark non-calculable when foreign FX is missing.

**Done when:** No historical foreign valuation uses future FX or identity 1.0 fallback.

### F03 | P1 | Benchmark price backfill

**Where:** `backend/transform/benchmark_transformer.py`.

**Problem:** Benchmark early-history gaps can be populated with future prices.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Use previous valid observed close only; leave pre-history unavailable; keep metadata filling separate from price filling.

**Done when:** Benchmark returns and alpha never use future closes.

### F04 | P1 | LTCG exemption leaks into unrelated tax classes

**Where:** `backend/engines/tax/core/liability.py`.

**Problem:** Listed-equity exemption can reduce foreign/gold/debt LTCG after classification is collapsed.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Retain eligible tax-class identity through set-off and liability; apply exemption only to eligible listed-equity pool.

**Done when:** Other LTCG classes never receive listed-equity exemption.

### F05 | P1 | Blended tax rates after set-off

**Where:** `backend/engines/tax/core/set_offs.py; liability.py`.

**Problem:** FY-level ST/LT pooling can lose which rate class remains taxable after losses.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Preserve class-specific taxable gain allocation after set-off and calculate using each class's actual rate. Keep one shared set-off engine.

**Done when:** Post-set-off tax agrees with class-specific eligible amounts and rates.

### F06 | P1 | Missing status/rate treated as tax-ready or zero

**Where:** `backend/engines/tax/core/liability.py`.

**Problem:** Null Tax_Status becomes READY and null Applied_Rate becomes 0.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Require explicit READY and valid rate for positive taxable amounts; reserve zero rate for intentionally exempt rules.

**Done when:** Missing tax evidence cannot publish as valid zero liability.

### F07 | P1 | FY tax state mixes uncertain and tax-ready gains

**Where:** `backend/engines/tax/core/fy_state.py`.

**Problem:** Gross ST/LT pools can include CHECK_REQUIRED rows while set-off excludes them.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Separate all observed/modelled from READY tax-calculable measures, or consistently restrict taxable measures to READY; keep uncertain exposure visible.

**Done when:** FY state and liability use explicitly reconcilable populations.

### F08 | P1 | Gold reconciliation repeats FY set-off and omits credits

**Where:** `backend/engines/tax/core/gold_formatter.py`.

**Problem:** FY set-off can be repeated across subhead rows; Tax_Credits hardcoded zero; Net_Taxable_Amount uses raw amounts.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Allocate set-off and credits to the declared grain, or keep FY-only components at FY grain; use post-set-off taxable amounts.

**Done when:** Summing detailed reconciliation rows produces correct FY totals.

### F09 | P1 | Forecast contract mismatch

**Where:** `backend/engines/tax/core/forecast.py`.

**Problem:** Realized-only monthly blended-rate projection is not hypothetical liquidation of tax-ready open lots.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Preserve realized-only planning as separately labelled output if needed; align Investment_Tax_Liability_Forecast with open-lot hypothetical liquidation, FY losses, class rates and uncertain exposure.

**Done when:** Forecast label, inputs and calculations match its stated purpose.

### F10 | P2 | Tax-credit reversal sign handling

**Where:** `backend/engines/tax/core/fy_state.py`.

**Problem:** abs(sum(credit amounts)) can obscure mixed-sign reversals.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Normalize credit/reversal semantics at event level before summing; do not apply absolute value to an arbitrary net sum.

**Done when:** Credits reflect net eligible withholding/payment including reversals.

### F11 | P2 | Identity caller field order

**Where:** `backend/utils/identity.py`.

**Problem:** v2 JSON encoding is unambiguous but dict insertion order can change IDs.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Fix ordered defining field schemas per namespace and reject missing/extra identity inputs. Coordinate any ID migration.

**Done when:** Refactoring dictionary construction cannot silently reidentify entities.

### F12 | P2 conditional | Synthetic reconciliation operation identity

**Where:** `backend/engines/analytics/core/fifo.py`.

**Problem:** Operation group identity may not distinguish repeated economically distinct synthetic additions.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Verify and enforce deterministic group identity plus stable within-group discriminator; preserve identity through mutation.

**Done when:** Distinct reconciliation additions never share Lot_ID.

### F13 | P2 | Malformed household amounts become zero

**Where:** `backend/transform/facts.py`.

**Problem:** strict=False casts followed by fill_null(0) may silently turn invalid money into zero.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Reject required malformed amounts or mark affected rows non-computable; preserve genuine zero.

**Done when:** Missing/malformed evidence is distinguishable from zero.

### F14 | P2 | Undefined return metrics shown as 0%

**Where:** `backend/engines/presentation/modules/investment_analytics.py`.

**Problem:** fill_null(0) on XIRR and related return fields erases undefined status.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Preserve nullable return metrics and existing statuses; only zero-fill genuinely additive monetary values.

**Done when:** Undefined returns never appear as valid 0%.

### F15 | P2 conditional | Snapshot database consistency boundary

**Where:** `backend/load/backup.py; backend/pipeline/etl_pipeline.py`.

**Problem:** File lock alone may not prevent an uncoordinated database writer during copy.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Verify all writers/connections are quiescent or use engine-supported consistent checkpoint/export. Preserve rollback semantics.

**Done when:** Snapshot has explicit database-consistency boundary.

### CG01 | P1 | Capital-gains group membership validation

**Where:** `backend/config/financial_rules.py`.

**Problem:** Duplicate sub_head_codes or ST/LT mismatches may pass; reverse lookup silently overwrites earlier groups.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Validate nonempty unique code membership across groups and consistency with gain_type.

**Done when:** Conflicting group definitions fail configuration loading.

### CG02 | P1 | Group name influences rates/exemption

**Where:** `backend/engines/tax/core/liability.py; forecast.py`.

**Problem:** Tax logic uses group-name keywords such as equity/foreign/gold.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Resolve rates from Tax_Sub_Head and macro parameters; encode eligible exemption explicitly, never infer from display/group names.

**Done when:** Renaming a group without changing codes/metadata never changes tax.

### CG03 | P1 | Incomplete group list makes valid tax subheads UNKNOWN

**Where:** `backend/engines/tax/core/base_events.py`.

**Problem:** Nonempty configured groups replace the complete supported subhead vocabulary.

**Impact:** This can affect correctness, explainability or reproducibility of financial outputs. The impact is conditional on the relevant input pattern unless explicitly established.

**Implementation:** Separate supported tax-code recognition from optional reporting grouping; validate required coverage if grouping must be exhaustive.

**Done when:** Valid investment tax codes remain recognized when optional groups are incomplete.

## Capital gains configuration contract

Keep `heads_of_income` UID-based (`cat_ids`, `sub_cat_ids`) for ledger income. Keep `capital_gains_groups` code-based (`sub_head_codes`, `gain_type`) for investment FIFO events. Do not add UID mappings to investment capital-gains groups. Group names are for grouping/presentation, not tax-law inference. Non-investment capital-asset ledger gains continue through the ledger mapping and supported default tax methods.

## Cross-cutting implementation rules

1. Preserve the existing Bronze/Silver/Gold structure, canonical purchase/sale grain, deterministic identity hierarchy and current useful calculations.
2. Do not add a new US-stock tax engine, new asset classes, a second set-off engine or a generalized rule framework.
3. Make a narrow producer-and-consumer change together: for example, changing Tax_Status requires checking liability, set-off, FY state, forecast and Gold.
4. Treat identity-definition changes as versioned migrations, not incidental refactors.
5. Confirm conditional risks before modifying behavior. No production data has been supplied to prove those scenarios occurred.

## Release closure

The v8.1.0 code hardening is ready to close when all applicable P1 findings are corrected, P2 items are either corrected or explicitly ruled out with code evidence, and the updated producers/consumers agree on tax eligibility, FX as-of semantics, financial identity and reconciliation grain. This is **not** the final QA sprint or documentation freeze.

## Out of scope

- Comprehensive automated tests, coverage targets and full golden regression suite.
- README, `/docs`, Wiki or profile README changes.
- New financial features, new asset classes, UI enhancements, tax-regime optimization or full ITR preparation.
- Performance optimization without a demonstrated regression.

## Evidence limitation

This plan consolidates findings from the previous v8.0.0 static archaeology and the subsequent capital-gains-group review. It is not an independent runtime certification of every listed issue. High-impact changes should be checked against their actual source call chains during implementation.
