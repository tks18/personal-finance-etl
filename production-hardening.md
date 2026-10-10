# Personal Finance ETL v7.0.0 — Targeted Code Hardening

**Baseline:** uploaded v7.0.0 source ZIP  
**Purpose:** close implementation defects and frozen-contract mismatches before documentation.  
**Excluded:** test-suite construction, golden scenarios, QA backlog, documentation polishing, speculative features.

This is a source-code review, not a successful production execution. **Confirmed** means the implementation issue is visible in code; **conditional** means the effect depends on actual data or the intended business contract. Make focused corrections, preserving the current architecture and existing valid outputs.

## 1. P1 — Ambiguous deterministic ID serialization

**Where:** `backend/utils/identity.py`, `generate_deterministic_id()`.

**Problem:** Canonical fields are serialized as `key=value` joined with `|`, without escaping or length framing. Distinct field maps can produce identical pre-hash payloads, for example `{"a":"x|b=y"}` and `{"a":"x","b":"y"}`. SHA-256 cannot distinguish equal input bytes.

**Impact:** The v1 identity contract is not unambiguous. Affected IDs could collide logically before hashing if delimiters appear in real identity fields.

**Implementation:** Use a versioned, unambiguous serialization (for example, UTF-8 canonical JSON array of ordered `[field_name, normalized_value]` pairs with an explicit namespace/version). Preserve numeric equivalence, NFC, null/date/currency rules. Do not silently change IDs: treat this as **Identity Serialization v2** and update every dependent producer together, including references across rebuilt Silver tables. Avoid a second independent hashing helper.

**Close when:** Every distinct typed field sequence has an unambiguous encoded payload and the identity-version transition is deliberate.

## 2. P1 — Gross capital gains and losses are netted before set-off reporting

**Where:** `backend/engines/tax/core/set_offs.py`, `_eager_process()`.

**Problem:** Events are grouped by `FY, Gain_Type` and `Realized_Gain_Loss` is summed to one signed value. The code then derives either gains or losses using `max(0, raw)` and `abs(min(0, raw))`. A FY containing both ST gains and ST losses loses the separate gross amounts before the detailed set-off fields are computed.

**Impact:** Even when net taxable gains happen to be correct, `STCL_Used_Against_STCG`, gross STCG/STCL, and downstream FY reconciliation can be understated or zeroed. The set-off engine cannot explain the actual flow of losses.

**Implementation:** Aggregate positive and negative events separately by FY and Gain_Type, producing independent non-negative `STCG`, `STCL`, `LTCG`, `LTCL` pools. Apply the existing ordered set-off and brought-forward logic to those pools. Keep the existing tax state schema and avoid creating a new tax subsystem.

**Close when:** Set-off output preserves gross gains, gross losses, amounts utilized and remaining balances rather than reconstructing them from a net signed number.

## 3. P1 — Tax classification is overwritten with calculation eligibility

**Where:** `backend/engines/tax/core/base_events.py`, `set_offs.py`, `liability.py`; forecast classification consumers.

**Problem:** For an unknown classification **or a synthetic reconciliation lot**, `base_events.py` replaces `Tax_Sub_Head` with `CHECK_REQUIRED`. Other processors then exclude these events by comparing `Tax_Sub_Head` to that string. The code already has a separate `Tax_Status` column.

**Impact:** Known tax classifications are lost for uncertain lots, while eligibility checks are coupled to a category label. This can distort breakdowns, reconciliation and future rules.

**Implementation:** Preserve the resolved `Tax_Sub_Head` when known. Set `Tax_Status=CHECK_REQUIRED` and a precise `Tax_Status_Reason` independently. Use `Tax_Status == READY` (plus valid amounts) as the tax-calculation eligibility gate in set-off, liability and Gold. If classification itself is unknown, keep a consistent unknown/null classification rather than inventing a tax sub-head named after status. Do not treat all reconciliation mutations as equivalent: retain the existing distinctions between synthetic lots, basis-adjusted lots and quantity-only removals.

**Close when:** Classification and eligibility are independent fields throughout tax calculation and presentation.

## 4. P1 — Missing foreign FX can proceed with invalid identity conversion

**Where:** `backend/engines/analytics/pipeline/processor/fx_gate.py` and its caller; downstream FX provider fallback.

**Problem:** `FXValidationGate.validate()` explicitly logs a warning and returns when a foreign-currency instrument has no FX provider. Its warning states that calculations can continue with `FX_Rate=1.0`, producing incorrect INR values. This is a direct conflict with the frozen foreign-FX safety contract.

**Impact:** Foreign asset values, cost basis, realized P&L and tax estimates can be materially wrong without a hard failure or an explicit non-calculable result.

**Implementation:** For non-base currencies, make missing/invalid FX a blocking condition for precise INR calculations. Prefer a domain-specific error or explicit unavailable status propagated through the existing worker/pipeline failure boundary. Reserve FX=1 exclusively for the configured base-currency identity pair. Do not silently publish precise foreign INR values after this gate fails.

**Close when:** No missing foreign FX provider/rate path can publish a precise value calculated with identity FX.

## 5. P1 — Future-looking FX backfill in historical dates

**Where:** `backend/transform/currency_transformer.py`.

**Problem:** The historical currency spine applies `.forward_fill().backward_fill().over("Currency_ID")`. If the first observation is later than the requested start date, the earlier dates inherit a future rate. `Is_Imputed` marks imputation but does not stop this rate from being consumed as historical evidence.

**Impact:** Acquisition-date basis, early valuations and tax-related FX conversion may use information unavailable on the relevant date.

**Implementation:** Keep backward-as-of/forward-fill from the latest **earlier** valid observation where the supported policy permits it. Do not backfill from future observations for historical financial calculations. Preserve an effective source observation date (or equivalent existing metadata). If no prior rate exists, leave it unavailable and let the FX eligibility boundary handle it. Avoid turning weekend/holiday gaps into errors when a valid preceding observation exists.

**Close when:** Every filled historical FX rate is traceable to an observation on or before its reporting date.

## 6. P1 — Investment tax forecast diverges from frozen hypothetical-liquidation semantics

**Where:** `backend/engines/tax/core/forecast.py`, `TaxLiabilityForecastBuilder.build()`.

**Problem:** The current table constructs a monthly projected tax bill from aggregated realized metrics and **blended rates** across configured capital-gains groups. It recomputes a simplified ST/LT set-off locally instead of using the dedicated set-off processor. `CHECK_REQUIRED` exposure is detected using `TAX_SUBTYPE == "CHECK_REQUIRED"`, which is not the independent tax-status contract.

**Impact:** Different tax classes can receive an artificial average rate; brought-forward losses and hypothetical open-lot liquidation may not be represented as frozen. Forecast totals may disagree with the FY tax engine.

**Implementation:** First preserve the useful existing monthly tax-planning behavior if it is a genuine supported consumer requirement. For the frozen `Investment_Tax_Liability_Forecast`, compute the **incremental hypothetical liquidation** of tax-ready open lots as of each forecast date, using each lot's actual tax classification, INR basis, forecast-date price/FX, and a copy of actual FY/carry-forward state. Reuse the common set-off methodology; do not write hypothetical events to actual Silver tax facts. Report uncertain lots separately by eligibility/status, not by overloading `TAX_SUBTYPE`. If the monthly cash-planning metric remains, give it a distinct semantic label rather than presenting it as hypothetical liquidation tax.

**Close when:** The forecast's title, inputs, rates, loss state and output all describe the same calculation, and uncertain lots never enter precise tax.

## 7. P2 — Synthetic reconciliation Lot_ID is not tied to its operation

**Where:** `backend/engines/analytics/core/fifo.py`, `buy()`.

**Problem:** For a lot without `purchase_id`, the generated Lot_ID hashes ISIN, date, quantity, price, currency and source type. It does not include the deterministic reconciliation group/event that created the synthetic quantity. Two distinct operations with identical values can generate the same Lot_ID.

**Impact:** Lot identity may be ambiguous, undermining lot-level reconciliation and realized-event uniqueness.

**Implementation:** Derive reconciliation-created Lot_ID from the deterministic `Reconciliation_Group_ID` and a stable within-group lot discriminator. Carry that identity through partial sale and basis/quantity mutations. Keep ordinary purchase-derived Lot_ID stable from `Purchase_ID`; do not use producing `Run_ID`, dataframe position or timestamp. Since existing IDs may change, coordinate with the identity-version change in item 1.

**Close when:** Separate reconciliation operations cannot create indistinguishable Lot_IDs, and one economic surviving lot retains its identity.

## Implementation order

1. **Identity:** Correct canonical serialization and synthetic lot derivation together as one intentional identity-contract migration.
2. **FX safety:** Remove missing-foreign-FX identity fallback and future-looking backfill.
3. **Tax correctness:** Preserve gross gain/loss pools, then separate Tax_Sub_Head from Tax_Status in all consumers.
4. **Forecast:** Align its meaning and calculations with the agreed investment liquidation contract, preserving distinct existing planning functionality if needed.
5. **Release closure:** Review changed contract schemas and producer/consumer interfaces for consistency; do not start the full QA sprint here.

## Explicitly not included

- Golden datasets, automated tests, full regression-suite construction, coverage targets or benchmark tasks.
- Documentation/README/Wiki updates.
- General refactoring, new tax-law engines, new asset classes, UI redesign or additional metrics.
- Unverified concerns such as performance, broker charges, and full FX P&L decomposition: investigate only if a concrete production mismatch is found.

## Release decision

**Needs targeted code hardening before documentation freeze.** Items 1–5 and 7 are directly supported by source inspection. Item 6 is a demonstrated mismatch with the previously frozen forecast contract, but its final change should preserve any intentional existing monthly planning use case. This is not a claim that the entire v7.0.0 application is broken, nor a certification of paths that have not been executed.
