# v9.1.0 — Typing & Documentation Evidence

| Measure | v9.0.1 |
| --- | ---: |
| `Any`-bearing lines | 277 |
| Files containing `Any` | 55 |
| `dict`/`Mapping` with `Any` | 147 |
| Files with mapping `Any` | 37 |
| `type: ignore` | 12 |
| Missing module docstrings | 0 |
| Missing public function docs | 59 |
| Missing public class docs | 37 |
| Missing public method docs | 46 |
| Packages with `__all__` | 38 / 42 |

## Highest-value typing hotspots

| Area | Evidence | Action |
| --- | --- | --- |
| `application/investments/isin_service.py` | ~56 `Any` lines | Finish typed financial/application records |
| `domain/investments/contracts.py` | ~25 | Tighten permissive v9.0 contracts |
| `application/investments/input_adapter.py` | ~10 | Type known instrument/master inputs |
| `domain/tax/events.py` | ~9 | Narrow stable event/input mappings |
| Operational edges | small residual | Keep dynamic state only where justified |

Most existing `type: ignore` annotations are credible third-party/library exceptions: markdown, customtkinter, yfinance, Numba and Polars schema casts.

Documentation debt is concentrated in FinancialRules/Pydantic models and high-value Quant/ingestion methods, making complete coverage realistic.
