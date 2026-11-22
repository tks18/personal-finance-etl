# Phase 016 - Settings UI, Recovery UX and CustomTkinter Retirement

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 015  
**Next:** Phase 017  
**Risk:** Medium-High

## 1. Outcome

Complete the operations console with Settings editing, recovery polish and removal of the legacy CustomTkinter UI/runtime dependencies.

## 2. Why this phase exists

- The UI migration is only complete when there is one desktop implementation and one source of presentation maintenance.
- Settings editing is valuable now because the configuration model has already been simplified and stabilized.

## 3. Inherited repository state

- Phase 015 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Phase-002 Settings model
- PySide6 views from 014–015
- CustomTkinter desktop package and tests
- pyproject/main.spec packaging
- recovery/snapshot services

## 5. Exact target state after this phase

Complete the operations console with Settings editing, recovery polish and removal of the legacy CustomTkinter UI/runtime dependencies.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Implement Settings view for approved operational/source paths, hash policies, log retention and related non-financial settings

Implement Settings view for approved operational/source paths, hash policies, log retention and related non-financial settings.

### Step 2 - Validate before save and show actionable field errors; keep FinancialRules read/validate/open-only

Validate before save and show actionable field errors; keep FinancialRules read/validate/open-only.

### Step 3 - Polish Recovery/Snapshot flows and destructive-action confirmation

Polish Recovery/Snapshot flows and destructive-action confirmation.

### Step 4 - Switch naked `pfetl` permanently to PySide6 and update presentation tests

Switch naked `pfetl` permanently to PySide6 and update presentation tests.

### Step 5 - Delete CustomTkinter UI modules, custom theme dependencies, tkcalendar/tkreload and packaging hooks if no surviving consumer needs them

Delete CustomTkinter UI modules, custom theme dependencies, tkcalendar/tkreload and packaging hooks if no surviving consumer needs them.

### Step 6 - Run packaged desktop smoke and full run/recovery/observability regression

Run packaged desktop smoke and full run/recovery/observability regression.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Legacy GUI/runtime dependencies are deleted only after parity is proven.

## 9. Tests and verification

- [ ] Only PySide6 desktop implementation remains.
- [ ] Settings saved by the GUI round-trip through the same Pydantic model used by CLI/runtime.
- [ ] FinancialRules are not edited by the GUI.
- [ ] No CustomTkinter/tk-specific dependency or command remains unless separately justified.
- [ ] Packaged GUI can run, diagnose, snapshot and restore the production workflow.

## 10. Explicit non-goals

- Do not add financial charts/KPIs or Analytics Studio functionality.
- Do not redesign FinancialRules.

## 11. Completion checklist

- [ ] Exit assertion: Only PySide6 desktop implementation remains.
- [ ] Exit assertion: Settings saved by the GUI round-trip through the same Pydantic model used by CLI/runtime.
- [ ] Exit assertion: FinancialRules are not edited by the GUI.
- [ ] Exit assertion: No CustomTkinter/tk-specific dependency or command remains unless separately justified.
- [ ] Exit assertion: Packaged GUI can run, diagnose, snapshot and restore the production workflow.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 017

The next phase may assume only the verified state above. It begins **Final Shan-First Acceptance and Analytics Studio Readiness** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 016
Status: Superseded / Pruned
Resolution: Formally pruned. Settings and snapshot/restore recovery operations are fully managed via `pfetl snapshot`, `pfetl restore`, and existing UI.
Exit assertions green: superseded
```
