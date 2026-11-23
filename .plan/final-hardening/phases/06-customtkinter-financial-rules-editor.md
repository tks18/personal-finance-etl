# Phase 06 — CustomTkinter Financial Rules Editor

**Sprint:** 2–3 hours  
**Goal:** provide the same safe profile-selection/edit/save experience for the complete FinancialRules model, including nested finance assumptions and guidance.

## Current model hierarchy

The editor must reflect the actual v11.3.1 model rather than a manually curated subset:

```text
FinancialRules
├── income
│   ├── active
│   ├── dividends
│   ├── interest
│   ├── non_cash
│   └── grouping              # added Phase 4
├── expense
│   ├── core
│   └── analytics             # added Phase 4
├── assets
│   ├── illiquid
│   ├── cashflow
│   └── digital
├── investments               # dict[str, InvestmentInstrumentRules]
├── assumptions
│   ├── macro
│   ├── fire
│   ├── monte_carlo
│   │   ├── markov_regime
│   │   ├── human_capital
│   │   ├── glide_path
│   │   ├── jump_diffusion
│   │   ├── guyton_klinger
│   │   └── inflation_model
│   ├── tax
│   │   ├── rates
│   │   ├── heads_of_income
│   │   ├── residual_income
│   │   ├── exempt_income
│   │   ├── investment_exclusions
│   │   └── ltcg_maturity_ladder_days
│   ├── cma
│   └── target_allocations
├── budget
├── portfolio_management
├── DEFAULT_CURRENCY_ID
└── MF_SCHEME_MAPPINGS
```

The UI must not silently omit a leaf that is editable in TOML.

## File/profile behavior

Reuse the same TOML persistence service created in Phase 5. Add façade methods:

```text
load_financial_rules_document(path)
save_financial_rules_document(path, values)
save_financial_rules_document_as(...)
```

Continue using `PreferencesManager.get_recent_rules/add_recent_rules`.

Header:

```text
[recent rules combo] [Browse] [Reload] [Validate] [Save] [Save As]
```

Selecting a rules file must update `rules_path_var` used by the Run tab.

## Field metadata pass

Many FIRE/Tax fields already have descriptions. Add descriptions to classification/mapping fields that currently lack them so the UI can explain:

- category/subcategory ID lists;
- cashflow role lists;
- investments mapping dict;
- `DEFAULT_CURRENCY_ID`;
- `MF_SCHEME_MAPPINGS`;
- target allocations;
- tax head/sub-head fields.

For percentages/rates, add `json_schema_extra={"ui_widget": "percentage"}` only when necessary to clarify decimal storage (e.g. `0.30 = 30%`). Keep stored values unchanged.

## UI sections

Use a scrollable section/subsection presentation, not one giant grid.

Recommended top sub-tabs within Financial Rules:

```text
Household | Investments | Tax | FIRE & Simulation | Mappings
```

### Household

- income classification lists;
- income grouping strings;
- expense core IDs;
- expense analytics windows/patterns/thresholds;
- asset classification lists;
- budget settings.

### Investments

- dynamic investment instrument mapping sections;
- portfolio management tolerance;
- CMA / target allocations if preferred here rather than FIRE.

### Tax

- debt cutoff date;
- harvest threshold;
- LTCG holding-period dict;
- exemption;
- rates;
- LTCG maturity ladder;
- head/sub-head configurations;
- exclusions.

### FIRE & Simulation

Render all existing macro, FIRE, Monte Carlo and stochastic models. Scalar fields are ordinary editors. For structured fields:

- Markov `transition_matrix` → 3x3 grid editor;
- `state_bull/bear/stag` tuples → three labeled numeric entries (drift, volatility, inflation target);
- target allocations → editable key/value rows with Add/Remove;
- dictionaries → key/value row editor;
- boolean glide-path option → switch.

### Mappings

- `DEFAULT_CURRENCY_ID`;
- `MF_SCHEME_MAPPINGS` key/value editor.

## Validation

Every save must run the complete Pydantic model validators, including:

- tax head/sub-head duplicate/overlap checks;
- investment exclusion mutual exclusivity;
- Phase-4 ladder validation;
- any new numeric bounds.

Where possible, display validation error path beside the relevant section rather than only a generic dialog.

`validate_investment_exclusion_uids()` requires a materialized income subcategory dimension and therefore remains a pipeline/data validation, not a pure file-editor validation. Explain this distinction in UI guidance; `pfetl doctor`/pipeline remains responsible for data-aware checks.

## Guidance UX

For every field show:

- human label;
- current value;
- model description;
- unit/interpretation;
- for rates, an example such as `0.05 = 5%` where helpful.

Do not reproduce long finance documentation. Two or three lines of contextual guidance is enough.

## Tests

- load/save full existing rules fixture with no semantic changes;
- edit one nested scalar and confirm fingerprint/model value changes;
- edit list/dict/matrix and round-trip;
- invalid tax overlap is blocked before write;
- invalid Markov dimensions or invalid new Phase-4 values are blocked;
- Save As + recent-rules behavior works.

## Exit criteria

Shan can manage multiple FinancialRules profiles entirely from the desktop UI, understand the meaning of every configurable field, edit complex structures safely, and switch the active profile used by the pipeline without source-code changes.
