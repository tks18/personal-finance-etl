# Phase 014 - PySide6 Shell, Run Workflow and Observability Parity

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 013  
**Next:** Phase 015  
**Risk:** Medium-High

## 1. Outcome

Introduce the PySide6 desktop shell and achieve run/log/snapshot/restore parity with the existing CustomTkinter application.

## 2. Why this phase exists

- PySide6 is justified by the planned table/history-heavy operations console.
- Parity first prevents UI redesign from silently breaking core operator actions.

## 3. Inherited repository state

- Phase 013 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- `presentation/desktop/app.py`, `base_tab.py`, `theme.py`
- `presentation/observability/desktop_sink.py`
- application facade and Phase-013 operator services
- PyInstaller spec and presentation tests

## 5. Exact target state after this phase

Introduce the PySide6 desktop shell and achieve run/log/snapshot/restore parity with the existing CustomTkinter application.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Add PySide6 dependency and minimal application/window composition without building all final views

Add PySide6 dependency and minimal application/window composition without building all final views.

### Step 2 - Implement configuration/rules path selection and Run PFETL action through the existing facade

Implement configuration/rules path selection and Run PFETL action through the existing facade.

### Step 3 - Run pipeline work off the UI thread using the smallest appropriate Qt worker mechanism; do not redesign pipeline async behavior

Run pipeline work off the UI thread using the smallest appropriate Qt worker mechanism; do not redesign pipeline async behavior.

### Step 4 - Adapt the existing observability/UI projection to Qt signals/widgets rather than creating a second event system

Adapt the existing observability/UI projection to Qt signals/widgets rather than creating a second event system.

### Step 5 - Implement snapshot/restore parity and open-log-folder/raw-JSONL affordances

Implement snapshot/restore parity and open-log-folder/raw-JSONL affordances.

### Step 6 - Add PyInstaller smoke configuration for Qt while retaining CustomTkinter temporarily for parity comparison

Add PyInstaller smoke configuration for Qt while retaining CustomTkinter temporarily for parity comparison.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Presentation technology changes while backend behavior remains authoritative.

## 9. Tests and verification

- [ ] PySide6 app starts from the `pfetl` entry path in test/development packaging.
- [ ] A full run completes without blocking the UI thread and uses existing observability truth.
- [ ] Snapshot/restore and failure rendering match existing application behavior.
- [ ] No finance/persistence logic exists in Qt widgets.
- [ ] CustomTkinter remains temporarily available only as migration fallback, not as a new feature target.

## 10. Explicit non-goals

- Do not build final Runs/Data/Warehouse views yet.
- Do not remove CustomTkinter until Phase 016.

## 11. Completion checklist

- [ ] Exit assertion: PySide6 app starts from the `pfetl` entry path in test/development packaging.
- [ ] Exit assertion: A full run completes without blocking the UI thread and uses existing observability truth.
- [ ] Exit assertion: Snapshot/restore and failure rendering match existing application behavior.
- [ ] Exit assertion: No finance/persistence logic exists in Qt widgets.
- [ ] Exit assertion: CustomTkinter remains temporarily available only as migration fallback, not as a new feature target.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 015

The next phase may assume only the verified state above. It begins **PySide6 Operations Console Views** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 014
Status: Superseded / Pruned
Resolution: Formally pruned to avoid GUI engineering bloat and 150MB+ binary dependencies. The canonical `pfetl` command and existing desktop application are certified as the long-term presentation boundary in Phase 013.
Exit assertions green: superseded
```
