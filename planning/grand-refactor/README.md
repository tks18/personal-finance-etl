# PFETL Grand Refactor

**Implementation baseline:** v9.5.3  
**Scope:** `personal-finance-etl` core only  
**Daily unit:** one phase, targeted at approximately 3-4 focused hours. High-risk cutover/certification phases may legitimately exceed that budget; never split them into unsafe half-states merely to hit the clock.  
**Rule:** every phase ends with a green, committable repository and a precise handoff to the next phase.

## How to work

1. Read `ARCHITECTURE.md` when a phase touches a boundary you have not worked on recently.
2. Open only the next unchecked phase file.
3. Implement the phase exactly through its completion checklist.
4. Run the phase-specific tests and gates.
5. Commit only after every exit assertion is true.
6. Mark the phase complete here and stop. The next phase may rely on the handoff state, not on unfinished local work.

If code evidence contradicts a phase, stop and amend the phase before changing the architecture. v9.5.3 is the historical implementation/regression oracle; after a phase is completed, its documented handoff becomes the starting-state authority for the next phase.

## Global invariants

- Financial methodology is not being generalized or made user-configurable.
- Existing deterministic PURCHASE, SALE, LOT, REALIZED, RECON and TAX identities are protected.
- Raw Store / Control Plane remains operational truth.
- Pre-Bronze will own source-shaped tabular evidence.
- Bronze will own PFETL canonical financial evidence.
- Silver will own canonical reconstructed financial state.
- Gold will own PFETL analytical/decision surfaces.
- Capability execution will ultimately be plan-driven, never scattered feature flags.
- Observability remains one emitter with its existing downstream consumers; only semantic context/events expand.
- Every dangerous migration follows expand -> migrate -> prove -> contract.

## Phase map

| Phase | Outcome | Target release | Status |
|---:|---|---|---|
| 001 | Canonical dataset identity and registry | v9.5.4 | [x] |
| 002 | Source identity and provider contracts | v9.5.4 | [x] |
| 003 | Typed dataset selectors and source-dataset contracts | v9.5.4 | [x] |
| 004 | Complete v9.5.3 topology as declarative configuration | v9.5.4 | [x] |
| 005 | Change-detection policy architecture | v9.5.5 | [x] |
| 006 | Change-detection runtime cutover | v9.5.5 | [x] |
| 007 | Bronze identity contract and strategy system | v9.5.6 | [x] |
| 008 | Canonical Silver/Gold semantic inventory | v9.6.0 | [x] |
| 009 | Source-independent financial classification | v9.6.1 | [x] |
| 010 | Canonical provenance model | v9.6.2 | [x] |
| 011 | Silver provenance cleanup | v9.6.2 | [x] |
| 012 | Provider-neutral market vocabulary | v9.6.3 | [x] |
| 013 | Canonical Silver vocabulary cutover | v9.6.4 | [x] |
| 014 | Capability graph | v9.7.0 | [x] |
| 015 | Execution planner and plan-scoped completeness | v9.7.1 | [x] |
| 016 | First optional capability proof | v9.7.2 | [x] |
| 017 | Production source configuration loader | v9.8.0 | [x] |
| 018 | Mapping and normalization engine | v9.8.1 | [x] |
| 019 | Identity integration and current mapping migration | v9.8.2 | [x] |
| 020 | Generalized configuration provenance | v9.8.3 | [x] |
| 021 | Pre-Bronze persistence foundation | v9.9.0 | [x] |
| 022 | Pre-Bronze operational and recovery integration | v9.9.1 | [x] |
| 023 | Pandera validation boundary | v9.9.2 | [x] |
| 024 | Source and first canonical Bronze validation contracts | v9.9.3 | [ ] |
| 025 | First generalized dataset vertical slice | v9.9.4 | [ ] |
| 026 | Typed DatasetCollection introduction | v9.9.5 | [ ] |
| 027 | DatasetCollection consumer migration and ExtractionResult demolition | v9.9.6 | [ ] |
| 028 | Household reference evidence migration | v10.0.0-rc1 | [ ] |
| 029 | Household transaction evidence and no-UID identity proof | v10.0.0-rc2 | [ ] |
| 030 | Reference evidence migration and column-master retirement | v10.0.0-rc3 | [ ] |
| 031 | Mutual-fund evidence migration | v10.0.0-rc4 | [ ] |
| 032 | Domestic-stock evidence migration | v10.0.0-rc5 | [ ] |
| 033 | US-investment evidence migration | v10.0.0-rc6 | [ ] |
| 034 | Provider-generated market evidence migration | v10.0.0-rc7 | [ ] |
| 035 | Fixed-topology demolition | v10.0.0-rc8 | [ ] |
| 036 | Strict canonical Bronze cutover | v10.0.0-rc9 | [ ] |
| 037 | Artifact-key operational provenance cutover | v10.0.0-rc10 | [ ] |
| 038 | Generalized ingestion certification | v10.0.0 | [ ] |
| 039 | Household and investment capability composition | v10.1.0 | [ ] |
| 040 | Benchmark and foreign-assets capability composition | v10.1.1 | [ ] |
| 041 | Tax capability composition | v10.1.2 | [ ] |
| 042 | Wealth, FIRE and simulation capability composition | v10.1.3 | [ ] |
| 043 | Plan-aware analytical warehouse | v10.2.0 | [ ] |
| 044 | Generalized recovery and replay semantics | v10.2.1 | [ ] |
| 045 | Core configuration diagnostics CLI | v10.3.0 | [ ] |
| 046 | External household topology certification | v10.3.1 | [ ] |
| 047 | External investment topology certification | v10.3.2 | [ ] |
| 048 | Generalized architecture performance hardening | v10.3.3 | [ ] |
| 049 | Public source-configuration contract freeze | v10.4.0 | [ ] |
| 050 | Fresh-install final PFETL acceptance | v10.4.1 | [ ] |

## Milestones

- **Foundation:** 001-007
- **Canonical financial model:** 008-013
- **Execution composition:** 014-016
- **Configurable evidence:** 017-020
- **Pre-Bronze + validation:** 021-024
- **First generalized production dataset:** 025
- **Typed dataset transport:** 026-027
- **Generalized ingestion cutover:** 028-038
- **Capability composition:** 039-043
- **Recovery + external usability + certification:** 044-050

## Batch authority

Phases 001-005 establish the gold-standard authoring benchmark.

Phases 006-010 are authored to the same rubric and extend the continuous handoff chain through canonical provenance.

Phases 011-015 preserve the same rigor through destructive Silver cleanup, provider-neutral vocabulary, canonical-model freeze, capability graph definition, and execution planning.

Phases 016-020 preserve the same rigor through the first optional runtime capability, production source configuration, mapping/normalization, identity integration, and configuration provenance.

Phases 021-025 preserve the same rigor through Pre-Bronze persistence/recovery, the Pandera trust boundary, and the first production dataset fully migrated through the generalized architecture.

Phases 026-030 preserve the same rigor through fixed-transport demolition, household generalization, alternate Bronze identity proof, reference migration, and column-master retirement.

Phases 031-035 preserve the same rigor through all investment/provider evidence migrations and complete fixed-topology demolition.

Phases 036-040 preserve the same rigor through strict canonical Bronze, operational provenance cutover, v10 generalized-ingestion certification, and the first major capability-composition releases.

Phases 041-045 preserve the same rigor through Tax/Wealth/FIRE composition, plan-aware physical warehouse state, generalized replay/recovery, and PFETL-native configuration diagnostics.

Phases 046-050 preserve the same rigor through external-user certification, performance hardening, public configuration freeze, and the final clean-install PFETL acceptance.

All 50 phases are specified and have passed the program-level QA described in `QA-REPORT.md`. Implementation remains phase-by-phase and every phase must finish green before the next begins.


## Grand Refactor completion definition

The program is complete only when Phase 050 passes without waived mandatory gates.

Completion does **not** include the future Config Studio, documentation portal, or analytics application. Those are separate applications/programs around the generalized PFETL core.

A future v11 is not implied by this plan. It requires a separately justified breaking product or public-contract boundary.
