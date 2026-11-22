# PFETL Grand Refactor

**Historical implementation baseline:** v9.5.3  
**Current implementation authority:** completed phase handoff through Phase 045 / v10.3.0  
**Scope:** `personal-finance-etl` core only  
**Daily unit:** one phase, targeted at approximately 3-4 focused hours. High-risk cutover and certification phases may exceed that budget; never split them into unsafe half-states merely to hit the clock.  
**Rule:** every phase ends with a green, committable repository and a precise handoff to the next phase.

## How to work

1. Read `ARCHITECTURE.md` whenever the active phase touches a boundary that has not been worked on recently.
2. Open only the next unchecked phase file.
3. Treat the previous completed phase handoff as the inherited-state authority.
4. Implement the active phase through its unique completion checklist. Do not pull work from the next phase forward.
5. Run the phase-specific tests, architecture guards and release gates.
6. Use the repository `pfetl-conventional-commits` Skill to preview and create semantically coherent commits. The phase file defines semantic boundaries; the Skill owns staging and Commitlint mechanics.
7. Mark the phase complete only after every exit assertion is true, then stop.

If code evidence contradicts a phase, stop and amend the owning phase or architecture specification before changing the design. v9.5.3 remains the historical regression oracle; after a phase is completed, that phase handoff becomes the starting-state authority for the next phase.

`PHASE-DEPENDENCY-MAP.csv` is the compact machine-readable phase ledger. It must stay consistent with this README and the phase files; it is not a competing architecture authority.

## Global invariants

- Financial methodology is not being generalized or made user-configurable.
- Same evidence + same `FinancialRules` + same enabled capabilities + same market evidence must produce the same financial truth.
- Deterministic `PURCHASE`, `SALE`, `LOT`, `REALIZED`, `RECON_LOT_GROUP`, `RECON_GROUP`, `RECON_EVENT` and `TAX` identities are protected.
- Raw Store / Control Plane remains operational truth.
- `SourceId` identifies configured physical evidence containers/provider configuration.
- `SourceBindingId` identifies configured physical tabular streams. It is not a canonical `DatasetId`.
- Pre-Bronze is source-shaped and keyed by `SourceBindingId` after the binding cutover.
- Bronze owns PFETL canonical financial evidence only. Source/vendor discriminator semantics must not survive merely for downstream interpretation.
- Silver owns canonical reconstructed financial state. Silver must not interpret source codes, file categories or vendor action strings.
- Gold owns PFETL analytical and decision surfaces.
- One binding may contribute to zero or many canonical datasets; one canonical dataset may be produced from zero or many bindings. N:M topology is first-class.
- Semantic interpretation is bounded and row-local. Configuration cannot execute arbitrary Python, SQL, Polars expressions, joins, aggregation or financial formulas.
- Canonical production owns fragment assembly, canonical identity, duplicate/grain enforcement, Gate 2 and canonical integrity. It does not own financial derivation.
- Capability planning and canonical satisfiability are separate concerns: capabilities say what evidence is required; satisfiability proves how current configuration can produce it.
- Bronze/Silver/Gold contracts converge to one authoritative `DatasetContract` universe before freeze. Pre-Bronze remains dynamic and source-configured.
- Observability remains one emitter with the existing downstream consumers. Only canonical/source-binding context expands.
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
| 024 | Source and first canonical Bronze validation contracts | v9.9.3 | [x] |
| 025 | First generalized dataset vertical slice | v9.9.4 | [x] |
| 026 | Typed DatasetCollection introduction | v9.9.5 | [x] |
| 027 | DatasetCollection consumer migration and ExtractionResult demolition | v9.9.6 | [x] |
| 028 | Household reference evidence migration | v10.0.0-rc1 | [x] |
| 029 | Household transaction evidence and no-UID identity proof | v10.0.0-rc2 | [x] |
| 030 | Reference evidence migration and column-master retirement | v10.0.0-rc3 | [x] |
| 031 | Mutual-fund evidence migration | v10.0.0-rc4 | [x] |
| 032 | Domestic-stock evidence migration | v10.0.0-rc5 | [x] |
| 033 | US-investment evidence migration | v10.0.0-rc6 | [x] |
| 034 | Provider-generated market evidence migration | v10.0.0-rc7 | [x] |
| 035 | Fixed-topology demolition | v10.0.0-rc8 | [x] |
| 036 | Strict canonical Bronze cutover | v10.0.0-rc9 | [x] |
| 037 | Artifact-key operational provenance cutover | v10.0.0-rc10 | [x] |
| 038 | Generalized ingestion certification | v10.0.0 | [x] |
| 039 | Household and investment capability composition | v10.1.0 | [x] |
| 040 | Benchmark and foreign-assets capability composition | v10.1.1 | [x] |
| 041 | Tax capability composition | v10.1.2 | [x] |
| 042 | Wealth, FIRE and simulation capability composition | v10.1.3 | [x] |
| 043 | Plan-aware analytical warehouse | v10.2.0 | [x] |
| 044 | Generalized recovery and replay semantics | v10.2.1 | [x] |
| 045 | Core configuration diagnostics CLI | v10.3.0 | [x] |
| 046 | Canonical contract and source-binding foundation | v10.3.1 | [x] |
| 047 | Source-binding configuration and compatibility compilation | v10.3.2 | [x] |
| 048 | Binding-aware source planning and Pre-Bronze cutover | v10.3.3 | [x] |
| 049 | Semantic interpretation and canonical route execution | v10.3.4 | [x] |
| 050 | Canonical production engine and Gate-2 integration | v10.3.5 | [x] |
| 051 | Canonical satisfiability planner and production graph | v10.4.0 | [x] |
| 052 | Household canonical evidence migration | v10.4.1 | [x] |
| 053 | Household Silver cutover and source-assumption demolition | v10.4.2 | [ ] |
| 054 | Investment, reference and provider canonical evidence migration | v10.5.0 | [ ] |
| 055 | Investment Silver cutover and legacy canonical demolition | v10.5.1 | [ ] |
| 056 | External household topology certification and column retirement | v10.5.2 | [ ] |
| 057 | External investment topology certification and column retirement | v10.5.3 | [ ] |
| 058 | Generalized architecture performance hardening | v10.5.4 | [ ] |
| 059 | Complete PFETL contract-universe freeze | v10.6.0 | [ ] |
| 060 | Final PFETL Core acceptance | v10.6.1 | [ ] |

## Milestones

- **Foundation:** 001-007
- **Canonical financial model:** 008-013
- **Execution composition:** 014-016
- **Configurable evidence:** 017-020
- **Pre-Bronze + validation:** 021-024
- **First generalized production dataset:** 025
- **Typed dataset transport:** 026-027
- **Generalized ingestion cutover:** 028-038
- **Capability composition + physical warehouse:** 039-043
- **Recovery + diagnostics:** 044-045
- **Canonical source-binding/composition architecture:** 046-051
- **Canonical household/investment migration:** 052-055
- **External topology certification:** 056-057
- **Performance hardening:** 058
- **Contract-universe freeze:** 059
- **Final Core acceptance:** 060

## Phase-authoring authority

Phases 001-045 remain the historical implementation chain that produced the v10.3.0 baseline.

Phases 046-051 repair the architectural seam discovered after Phase 045: physical source bindings and PFETL canonical evidence become separate first-class concepts; Pre-Bronze becomes binding-keyed; source semantics become bounded routes; fragments assemble through canonical production; and satisfiability planning proves the required canonical evidence can be produced before execution.

Phases 052-055 migrate the Shan household and investment/reference/provider paths onto that architecture while preserving financial outputs and protected identities. Phase 055 removes the migration-only compatibility path so certification inherits exactly one production architecture.

Phases 056-057 certify genuinely different external household and investment topologies and perform consumer-backed column-retirement archaeology. These phases may repair defects exposed by certification, but they must not invent a second architecture or hide fixture-specific assumptions.

Phase 058 profiles the final architecture only after topology certification. Phase 059 freezes one extraction-ready contract universe for identifiers, configuration, capabilities and complete Bronze/Silver/Gold dataset contracts. Phase 060 certifies both clean installation and supported upgrade from representative v10.3.0 operational state.

The phase files are implementation authorities, not release-note summaries. Each completion checklist is a unique exit contract for the next phase.

## Grand Refactor completion definition

The program is complete only when Phase 060 passes without waived mandatory gates.

At that point PFETL Core must support heterogeneous supported source topologies through configuration while keeping financial meaning, deterministic downstream identities, recovery semantics and observability under PFETL ownership. The physical warehouse must match the active effective DatasetContracts, and the same financial evidence must converge to the same Silver/Gold truth regardless of supported source topology. All built-in PFETL Core user surfaces—including the Tkinter Desktop GUI (`presentation.desktop`) and Terminal CLI (`presentation.cli`)—are fully modernized, clean, and integrated with the diagnostics and capability suites.

Completion does **not** include external standalone tools such as Config Studio, Analytics Studio, the dedicated documentation portal or contract-package extraction. Those are separate ecosystem programs after Core acceptance.

A post-060 ecosystem-readiness archaeology may determine that the internal contract modules are ready to extract into `pfetl-contracts`. Do not introduce a Phase 061 merely to perform extraction if the Phase-059 freeze already made the boundary mechanically separable.
