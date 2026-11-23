# Phase 02 — Publish, Integrate PFETL and Delete Duplication

**Timebox:** 2–3 focused hours  
**Authority:** Program `README.md` + this phase file  
**Prerequisite:** Phase 01 exit criteria are green

## 1. Outcome

Publish the first standalone Project Forge release, make PFETL the first real consumer, remove duplicated reusable script implementations from PFETL, and leave PFETL with only application-specific automation.

At phase exit, future repositories such as PFETL Analytics Studio can install Project Forge instead of copying PFETL's current `scripts/` utilities.

## 2. Pre-publication checks in Project Forge

Before publishing:

1. Verify final distribution name availability.
2. Confirm package metadata:
   - name;
   - version;
   - description;
   - license;
   - Python requirement;
   - repository URL;
   - classifiers where useful.
3. Register CLI entrypoint:

```toml
[project.scripts]
pforge = "project_forge.cli:app"
```

4. Run complete focused test suite.
5. Run Project Forge against its own repository:

```text
pforge doctor
pforge status
pforge quality --fast
pforge commit --preview
pforge changelog validate
```

6. Build package:

```text
uv build
```

7. Install the built wheel in a clean environment or temporary `uv` environment and verify `pforge --help`.

## 3. First release

Set initial public version to:

```text
0.1.0
```

Publish using the normal secure PyPI mechanism configured for the environment. Do not embed credentials in Project Forge source/configuration.

Verify after publication:

- package installs by distribution name;
- `pforge --version`/version display resolves the published version;
- CLI help renders;
- README/package metadata render correctly on PyPI.

If public publication is intentionally delayed, a local/private wheel may be used for the PFETL integration step, but the phase is not fully complete until the intended first release is published.

## 4. Add Project Forge to PFETL development tooling

In the post-Core-hardening PFETL repository:

- add Project Forge as the appropriate development dependency/tool dependency;
- configure `[tool.project-forge]` in `pyproject.toml` for PFETL's actual source/test/changelog/branch conventions;
- configure PFETL's desired quality tiers;
- configure documentation ownership audit only if still useful after the Core maintenance batch;
- configure commit header length/scope overrides only where necessary.

Prefer configuration over PFETL-specific code forks.

## 5. Dogfood every migrated workflow in PFETL

Run, at minimum:

```text
pforge doctor
pforge status
pforge quality --fast
pforge quality
pforge commit --preview
pforge changelog validate
pforge pr preview
pforge release preview
pforge hooks status
```

Do not create/publish external artifacts merely for testing. Use preview/dry-run paths unless an actual PR/release is intended.

Compare behavior with the current PFETL scripts before deleting them.

## 6. Replace PFETL wrappers

Where PFETL currently exposes reusable scripts through Poe/package commands, change them to call `pforge` rather than local Python modules.

Examples:

```text
audit-fast  -> pforge quality --fast
audit-full  -> pforge quality
commit      -> pforge commit
PR preview  -> pforge pr preview
release     -> pforge release ...
```

Poe may remain if PFETL still uses it for application-specific tasks. It is no longer the implementation host for generic project tooling.

Do not keep wrappers whose only purpose is to rename an identical `pforge` command unless they materially improve the PFETL workflow.

## 7. Replace hooks

Use Project Forge-managed hooks rather than the current PFETL-specific generated hook content.

Verify:

```text
pre-commit -> pforge quality --fast
pre-push   -> pforge quality
```

or the exact configured equivalent.

The hooks must no longer contain:

```text
Personal Finance ETL
uv run poe audit-fast
uv run poe audit-full
```

## 8. Delete migrated PFETL implementations

After dogfooding confirms equivalent behavior, delete the reusable local implementations:

```text
scripts/quality_gate.py
scripts/auto_commit.py
scripts/create_pr.py
scripts/create_releases.py
scripts/install_hooks.py
scripts/audit_documentation.py
```

Refactor/delete the reusable portions of:

```text
scripts/tasks.py
```

Do **not** delete PFETL-specific automation merely because it lives under `scripts/`.

The current explicit PFETL-only example is:

```text
scripts/run_pipeline.bat
```

Any remaining PFETL-specific build/run helper may remain if the Core hardening program still uses it.

If `scripts/__init__.py` becomes unnecessary, remove it with the package structure.

## 9. Remove stale PFETL references

Search the entire PFETL repository for references to deleted modules/functions, including:

```text
quality_gate
auto_commit
create_pr
create_releases
install_hooks
audit_documentation
scripts.tasks
```

Update/remove references in:

- `pyproject.toml`;
- `poe_tasks.toml`;
- `package.json` if still present after Core cleanup;
- Git hooks;
- README;
- contributor/release instructions;
- automation scripts.

Do not leave zombie commands pointing to deleted files.

## 10. Preserve application-specific behavior

This extraction must not change PFETL runtime behavior.

Do not modify:

- financial pipeline;
- Settings/FinancialRules semantics;
- warehouse;
- Control Plane;
- observability;
- CustomTkinter runtime;
- application packaging, except where project tooling references are being removed.

This phase is developer-tooling integration only.

## 11. PFETL verification

Run PFETL's post-hardening confidence suite and the relevant developer workflow:

```text
pforge quality --fast
pforge quality
```

Then verify:

- PFETL tests remain green;
- `pfetl` runtime CLI still works;
- no Project Forge import exists in PFETL production runtime packages unless explicitly justified;
- Project Forge is development/repository tooling, not a runtime financial dependency.

## 12. Release/dogfood feedback rule

If PFETL exposes a generic defect in Project Forge:

1. fix it in Project Forge;
2. add/adjust Project Forge tests;
3. release a patch version (`0.1.x`);
4. upgrade PFETL;
5. do not add a PFETL-only workaround unless the behavior is genuinely PFETL-specific.

This is the key rule that keeps the extraction useful.

## 13. Analytics Studio readiness

At the end of this phase, record the minimal usage expected for the future Analytics Studio repository:

```text
install project-forge
configure [tool.project-forge]
use pforge quality/commit/hooks/pr/release/publish
```

Do not add Analytics Studio-specific behavior to Project Forge before Studio actually needs it.

## 14. Explicit non-goals

Do not:

- redesign PFETL's application architecture;
- turn Project Forge into a PFETL dependency at runtime;
- add new Project Forge features unrelated to replacing current duplicated scripts;
- manufacture `0.2.0`/`0.5.0` releases during this phase;
- add CI-provider abstractions;
- migrate PFETL-specific `run_pipeline.bat` into Project Forge.

## 15. Exit criteria

Phase 02 is complete only when:

- [ ] first Project Forge release is published at `0.1.0` or an explicitly approved equivalent name/version;
- [ ] clean install exposes `pforge`;
- [ ] PFETL installs/configures Project Forge successfully;
- [ ] `pforge doctor` and `pforge status` work inside PFETL;
- [ ] fast/full quality workflows work inside PFETL;
- [ ] commit preview works against real PFETL changes;
- [ ] changelog/PR/release preview workflows work inside PFETL;
- [ ] hooks are Project Forge-driven;
- [ ] reusable local PFETL script implementations are removed;
- [ ] PFETL-specific automation remains where appropriate;
- [ ] no stale repository references point to deleted scripts;
- [ ] PFETL production confidence tests remain green;
- [ ] PFETL runtime/financial behavior is unchanged;
- [ ] any generic integration defects were fixed upstream in Project Forge rather than patched locally.

## 16. Program completion

After this phase:

```text
PFETL Core         -> consumes Project Forge for repository workflows
Analytics Studio   -> can start with Project Forge from day one
Project Forge      -> owns shared engineering-tooling behavior
```

The extraction program is complete. Further Project Forge enhancements should be driven by real reuse across repositories, not speculative feature expansion.
