---
name: pfetl-conventional-commits
description: >-
  Use this skill when preparing, previewing, or executing Git commits adhering to Commitlint
  and Conventional Commits, using .commit_overrides.json, or managing Git hooks.
---

# PFETL Conventional Commits & Automation Runbook

This skill outlines how to stage and commit files using the automated Conventional Commit tool (`scripts/auto_commit.py`), enforce Commitlint standards, and configure commit overrides.

---

## 1. Commit Commands Overview (`poe_tasks.toml`)

All commit workflows are executed via `uv run poe`:

| Task | Command Flag | Behavior |
|---|---|---|
| `uv run poe commit:preview` | `--preview` / `--dry-run` | Dry-run preview of semantic file groupings and generated commit messages. No changes staged or committed. |
| `uv run poe commit:run` | `--run` | Automatically commits file-by-file without interactive prompts. Runs upfront Fast Quality Gate. |
| `uv run poe commit:interactive` | `--interactive` / `-i` | Interactive file-by-file wizard with diff inspection and prompt choices. |
| `uv run poe commit:overrides` | `--run` with `.commit_overrides.json` | Commits explicitly grouped files mapped to custom commit messages. |
| `uv run poe commit:overrides:preview` | `--preview` with `.commit_overrides.json` | Dry-run preview of commit overrides without touching Git state. |
| `uv run poe commit:overrides:only` | `--overrides-only` | Executes commits *only* for files specified in `.commit_overrides.json`. |

---

## 2. Commitlint Formatting Rules

Every commit message must strictly comply with Conventional Commits and Commitlint:

- **Format:** `<type>(<scope>): <subject>`
- **Length:** The header line must be **strictly <= 72 characters**.
- **Case:** Lowercase subject, no trailing punctuation.
- **Valid Types:**
  - `feat`: New feature or user-facing capability.
  - `fix`: Bug fix.
  - `docs`: Documentation updates.
  - `style`: Formatting, missing semicolons, whitespace (no code change).
  - `refactor`: Code refactoring without behavioral change.
  - `perf`: Performance improvement.
  - `test`: Adding or fixing tests.
  - `build`: Build system or dependency updates (`pyproject.toml`, `uv.lock`).
  - `ci`: CI/CD workflows or GitHub Actions.
  - `chore`: Maintenance tasks, config tweaks, internal tools.

### Valid Examples
- `docs(agents): add workspace agents.md rulebooks` (47 chars)
- `refactor(pipeline): extract lifecycle coordinator from executor` (63 chars)
- `test(tax): add fy2024 stcg slab validation tests` (47 chars)
- `fix(fifo): resolve shadow lot unit rounding discrepancy` (55 chars)

---

## 3. Configuring `.commit_overrides.json`

For multi-file atomic changes that belong to a single semantic commit, define them in `.commit_overrides.json` at the repository root:

```json
{
  "docs(agents): add root and workspace agents.md guidelines": [
    "AGENTS.md",
    "tests/AGENTS.md",
    "scripts/AGENTS.md"
  ],
  "feat(agents): add pfetl agent skills suite": [
    ".agents/skills/pfetl-pipeline-diagnostics/SKILL.md",
    ".agents/skills/pfetl-quality-and-release/SKILL.md",
    ".agents/skills/pfetl-conventional-commits/SKILL.md"
  ]
}
```

### Applying Overrides
```powershell
# 1. Preview how the overrides will be staged
uv run poe commit:overrides:preview

# 2. Execute the commit overrides
uv run poe commit:overrides
```

---

## 4. Quality Gate Integration & Atomic Bypass

1. **Pre-Commit Verification:**
   Before staging files, `auto_commit.py` automatically runs the Fast Quality Gate (`uv run poe audit-fast`). If lint or type checks fail, the commit process halts immediately.
2. **Atomic `--no-verify` Bypass:**
   Because `auto_commit.py` already verified the full working tree upfront, it commits individual atomic groups using `--no-verify`. This prevents repetitive, blocking Git hooks from running on partial slices of unstaged files.

---

## 5. Installing or Resetting Git Hooks

To install or refresh the pre-commit and pre-push quality hooks in `.git/hooks/`:

```powershell
uv run poe install-hooks
```
