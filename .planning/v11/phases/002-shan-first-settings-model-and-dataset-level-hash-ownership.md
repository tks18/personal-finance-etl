# Phase 002 - Shan-First Settings Model and Dataset-Level Hash Ownership

**Target release:** v11.1.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 001  
**Next:** Phase 003  
**Risk:** Medium

## 1. Outcome

Replace historical uppercase Settings fields and file-type hash policy with a small Shan-first typed settings model while reproducing current runtime behavior.

## 2. Why this phase exists

- The current `Settings` mixes locations, Raw Store, dependencies, statements, hashing and observability using historical uppercase names.
- Hashing is currently owned by file type even though change policy is evidence-specific.
- This phase changes configuration ownership and naming only; it must not redesign ingestion.

## 3. Inherited repository state

- Phase 001 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- `config/settings.py::Settings` and `FileHashPolicy`
- `tests/config.toml` and configuration provenance tests
- `infrastructure/control_plane/hashing.py::FILE_TYPE_MAP`
- file-sync/hash consumers
- `infrastructure/warehouse/contracts.py::BronzeDataContract.is_full_replace`

## 5. Exact target state after this phase

Replace historical uppercase Settings fields and file-type hash policy with a small Shan-first typed settings model while reproducing current runtime behavior.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Define shallow typed groups for runtime paths, sources and observability; retain `FinancialRules` separately

Define shallow typed groups for runtime paths, sources and observability; retain `FinancialRules` separately.

### Step 2 - Use lowercase Python field names; retain uppercase only for environment-variable compatibility if used

Use lowercase Python field names; retain uppercase only for environment-variable compatibility if used.

### Step 3 - Represent the nine frozen source/location concepts from the decision ledger, keeping one `statements_root`

Represent the nine frozen source/location concepts from the decision ledger, keeping one `statements_root`.

### Step 4 - Introduce evidence-source hash policy with only `NONE` and `CONTENT`; migrate current CSV=True / Excel=False / SQLite=False behavior without semantic change

Introduce evidence-source hash policy with only `NONE` and `CONTENT`; migrate current CSV=True / Excel=False / SQLite=False behavior without semantic change.

### Step 5 - Keep provider/parser and full/incremental load behavior code-owned; do not expose load mode as user configuration

Keep provider/parser and full/incremental load behavior code-owned; do not expose load mode as user configuration.

### Step 6 - Update validation, settings flattening/auditing and configuration snapshots

Update validation, settings flattening/auditing and configuration snapshots.

### Step 7 - Provide one explicit v11 config migration example/test from old TOML to new TOML shape

Provide one explicit v11 config migration example/test from old TOML to new TOML shape.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Configuration provenance and hash resolution change ownership; source semantics remain fixed.

## 9. Tests and verification

- [x] The new Settings model loads a migrated production-shaped config successfully.
- [x] Current hash-enabled/hash-disabled behavior is reproduced for every known source category.
- [x] No runtime consumer reads the old `FILE_HASH_POLICY.csv/excel/sqlite` model.
- [x] `FinancialRules` remains a separate configuration authority.
- [x] Settings snapshots remain auditable after the nested-name change.

## 10. Explicit non-goals

- Do not change source formats, folder-discovery semantics, Bronze table names, load semantics or Control Plane schema.
- Do not introduce generic source descriptors/selectors.

## 11. Completion checklist

- [x] Exit assertion: The new Settings model loads a migrated production-shaped config successfully.
- [x] Exit assertion: Current hash-enabled/hash-disabled behavior is reproduced for every known source category.
- [x] Exit assertion: No runtime consumer reads the old `FILE_HASH_POLICY.csv/excel/sqlite` model.
- [x] Exit assertion: `FinancialRules` remains a separate configuration authority.
- [x] Exit assertion: Settings snapshots remain auditable after the nested-name change.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 003

The next phase may assume only the verified state above. It begins **Reference Data Cleanup and Instrument Master Migration** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 002
Target release: v11.1.0
Files changed:
- src/personal_finance_etl/config/settings.py
- src/personal_finance_etl/config/__init__.py
- src/personal_finance_etl/infrastructure/providers/files/locator.py
- src/personal_finance_etl/infrastructure/control_plane/file_sync.py
- src/personal_finance_etl/infrastructure/warehouse/meta/layer.py
- src/personal_finance_etl/infrastructure/observability/redaction.py
- src/personal_finance_etl/application/facade.py
- src/personal_finance_etl/application/ingestion/coordinator.py
- src/personal_finance_etl/application/pipeline/execution.py
- src/personal_finance_etl/application/pipeline/lifecycle.py
- src/personal_finance_etl/application/pipeline/orchestrator.py
- src/personal_finance_etl/bootstrap/container.py
- tests/config.toml
- tests/test_configuration_provenance.py
- tests/test_forensic_pipeline.py
- tests/test_legacy_logging_demolition.py
- tests/test_phase2_config_and_primitives.py
- tests/test_phase9_orchestration_and_bootstrap.py
- tests/test_redaction_and_retention.py
External files migrated:
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/ETL App/shan_personal_finance_ETL.toml
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/ETL App/shan_personal_finance_ETL_Test.toml
Contracts/schema changed: Strict v11 typed Settings schema with 5 groups ([database], [sources], [statement_patterns], [hash_policy], [observability]) and extra='forbid'
Financial formulas changed: None
Protected identity comparison: N/A
Focused tests: 195/195 passed (including config provenance, primitives, forensic pipeline, and lifecycle)
Architecture tests: tests/test_architecture_boundaries.py (passed)
Real-data verification: Loaded and validated shan_personal_finance_ETL.toml and shan_personal_finance_ETL_Test.toml against live Google Drive paths
Power BI verification: N/A
Observability/recovery verification: Strict typed fingerprinting and logging retention verified in tests/test_forensic_pipeline.py and test_redaction_and_retention.py
Static analysis verification:
- pyright: 0 errors, 0 warnings, 0 informations
- pylint src: 10.00/10 rating
- mypy: no issues found in 199 source files
- ruff: all checks passed, formatting clean
- documentation: 100% documented, zero AST audit violations
Compatibility/transitional state remaining: None. All legacy flat keys, normalizers, and UPPERCASE property shims completely eradicated.
Semantic commit groups:
- refactor(config): implement strict v11 typed settings schema and parameterize statement patterns
- refactor(core): migrate pipeline, coordinator, container, and meta to typed settings attributes
- test(config): update test fixtures and provenance suites to strict typed settings models
Exit assertions green: yes
```
