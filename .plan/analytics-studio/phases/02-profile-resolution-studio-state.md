# Phase 02 — PFETL Profile Resolution and Studio State

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 01.

## Phase outcome
Use the exact PFETL Settings TOML + FinancialRules TOML pair as a Studio profile, resolve all upstream paths without importing Core, and persist only Studio-owned recent-profile/preferences state.

## Inherited state
- The app/CLI and package layout exist.
- Studio owns no configuration TOML of its own.

## Files in scope
- `src/pfetl_analytics_studio/profile.py`
- `src/pfetl_analytics_studio/state.py`
- `tests/test_profile_connections.py`
- small updates to `cli.py`/`app.py` only to accept/select a profile

## Grounded PFETL / Studio inputs
- Settings TOML keys under `database`, `sources`, `observability` described in README §2.1.
- FinancialRules TOML is a second independent path; Studio reads it for profile identity/context but does not validate Core methodology in full.
- Resolved PFETL files: `<target_db_base_path>/<target_db_name>`, `<target_db_base_path>/<raw_document_store_name>`, resolved logs directory, `<target_db_base_path>/pipeline.lock`.

## Required contracts at phase exit
- Frozen Pydantic `PFETLProfile` with `settings_path`, `rules_path`, resolved `duckdb_path`, `control_plane_path`, `logs_path`, `lock_path`, `profile_id`.
- `ProfileLoadResult`/typed error state distinguishing missing TOML, malformed TOML, missing required database settings, and unresolved paths.
- `StudioStateStore` owning `studio.sqlite` under `platformdirs.user_data_dir("PFETL Analytics Studio")`.
- Studio tables: `recent_profiles(profile_id, settings_path, rules_path, last_opened_at)`, `app_preferences(key, value)`; additive schema version integer.

## Data and query semantics
- `profile_id` is deterministic from normalized absolute Settings+Rules paths, not from their contents.
- Read TOML with `tomllib`; never rewrite it.
- Resolve relative `observability.logs_directory` against `target_db_base_path` exactly as PFETL does.
- Do not require source files to exist merely to open Studio; database/control-plane availability is checked in Phase 03.

## UI / interaction specification
- Startup shows recent profile pairs and “Open profile”.
- Selecting a pair displays resolved PFETL paths and any parse/path warning before database access.
- Remember successful profile selections only; malformed pairs are not promoted to recents.

## Implementation sequence
1. Implement raw TOML readers and path normalization.
2. Implement `PFETLProfile.load(settings_path, rules_path)` producing the resolved immutable profile.
3. Create/open Studio-owned SQLite and additive schema bootstrap without Alembic.
4. Implement recent-profile CRUD and one preference getter/setter used later for output directory or last profile.
5. Wire profile selection into the shell without querying PFETL databases.
6. Test deterministic profile identity and recent ordering.

## Focused verification
- Fixture TOMLs resolve expected database/log/lock paths.
- Studio SQLite writes are confined to its own temp path.
- Opening a profile does not modify either TOML (hash before/after).

## Edge cases and failure behaviour
- Missing Settings or Rules file: typed invalid-profile state.
- Malformed TOML: show parse error with file name, not traceback.
- Empty `target_db_base_path`: profile loads with validation issue; do not guess a data location.
- Windows paths and spaces must be handled through `pathlib.Path`.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not clone PFETL Pydantic Settings/FinancialRules classes into Studio; parse only the leaves needed for location/context at this boundary.

## Exit criteria
- [ ] Profile pair is the only user-selected upstream configuration.
- [ ] Studio state DB is created separately from PFETL storage.
- [ ] Recent profile pairs survive restart.
- [ ] Selected TOMLs remain byte-identical after tests/runtime.

## Handoff to next phase
Phase 03 may assume one resolved immutable profile and a Studio-owned state store.
