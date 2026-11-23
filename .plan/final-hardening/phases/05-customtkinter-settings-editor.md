# Phase 05 — CustomTkinter Settings Editor

**Sprint:** 2–3 hours  
**Goal:** make any selected Settings TOML fully editable and safely saveable from the existing CustomTkinter application while preserving recent-file behavior.

## Current UI anchors

`UnifiedETLTab` currently owns:

- `config_path_var` and recent-config combo box;
- `_on_config_selected()` which calls `engine.validate_config()` and records recents;
- `_select_file()` native picker;
- Run/Snapshot/Restore and narrative log.

Do not discard those behaviors. Move them into a cleaner tab structure.

## Minimal new infrastructure

Add `tomlkit` dependency for comment/order-preserving TOML edits.

Add a small application/facade capability, not presentation-owned file writing:

```text
PersonalFinanceEngine.load_settings_document(path)
PersonalFinanceEngine.save_settings_document(path, values)
PersonalFinanceEngine.save_settings_document_as(source_path, target_path, values)
```

Implementation may use a small infrastructure helper such as:

```text
infrastructure/configuration/toml_store.py
```

Responsibilities:

- parse TOML document with tomlkit;
- merge validated model values into existing document;
- write to temporary sibling file;
- reload with `Settings.from_toml`;
- atomic replace only after reload succeeds.

Do not expose tomlkit objects to presentation.

## Settings field metadata

Before building widgets, add `Field(description=...)` to existing Settings fields that lack useful descriptions:

- database paths/names and `disable_file_discoverer`;
- all nine sources;
- statement patterns;
- hash policy fields;
- observability fields;
- Phase-4 performance/market-data fields.

UI labels can derive from field names (`target_db_base_path` → `Target DB Base Path`) with optional `title=` for better wording.

## Desktop structure

Refactor `presentation/desktop/app.py` so root window owns navigation rather than all controls. Create:

```text
run_tab.py
settings_tab.py
config_editor.py
```

Do not rewrite `base_tab.py` observability handling in this phase.

Use `CTkTabview` or equivalent top navigation. At minimum expose `Run` and `Configuration`; Phase 7 adds Logs/System.

## Settings editor behavior

Header controls:

```text
[recent config combo] [Browse] [Reload] [Save] [Save As]
```

Sections rendered in current Settings order:

1. Database
2. Sources
3. Statement Patterns
4. Hash Policy
5. Observability
6. Performance
7. Market Data

Widget inference:

- `bool` → switch/checkbox;
- `StrEnum` → combo box;
- `int/float` → text/numeric entry with validation on save;
- `str` path under Sources/Database/logs → entry + file/directory browse button according to field meaning;
- `list[str]` → comma/newline editor for US statement patterns;
- nullable integer (`max_age_days`) → entry supporting blank = `None`.

Each row shows:

```text
Label
Editor
short description/help text
validation error area when invalid
```

Do not show raw Pydantic syntax.

## Selection and recent files

When a user chooses a config through combo/browse:

1. load `Settings.from_toml`;
2. if valid, populate editor;
3. add to recents;
4. refresh combo values;
5. update `config_path_var` used by Run/Snapshot/Restore.

If invalid, do not replace the currently loaded editor state; show the parsing/validation error.

## Save behavior

On Save:

1. collect all field values;
2. construct nested dict matching Settings schema;
3. `Settings.model_validate(values)`;
4. show all validation failures without writing;
5. persist atomically through façade/helper;
6. reload from disk;
7. add path to recents;
8. show success state.

`validate_config()` currently only parses Settings and does not call `validate_config()` path existence checks. Keep two UI actions distinct:

- **Validate syntax/model** for editing;
- **Run/Doctor readiness** can perform filesystem validation.

## Low-maintenance constraints

- one reusable `ConfigFieldEditor` is acceptable;
- no generic form framework;
- no external JSON schema file;
- no custom Settings duplicate model in presentation;
- no direct file writes from widgets.

## Tests

Add focused tests to the minimal suite for:

- Settings save round trip;
- comment/order preservation for a representative TOML;
- invalid edit never overwrites original;
- Save As produces an independently loadable Settings file;
- recent config list updates.

Avoid pixel/UI automation.

## Exit criteria

Shan can select any valid Settings TOML, understand every field, edit it, validate it, Save/Save As, and immediately run PFETL using that selected profile without editing TOML manually.
