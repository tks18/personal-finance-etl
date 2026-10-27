Fix ISIN worker-returned traceback ownership
File: src/personal_finance_etl/application/investments/isin_service/pipeline.py
In the branch handling the worker-returned error_info, stop creating ErrorDetails via ErrorDetails.create(RuntimeError(...)), because there is no active exception there and traceback.format_exc() can become "NoneType: None". Instead, construct the ErrorDetails using the worker's existing error_info["traceback"] as traceback_summary. Then remove the separate diagnostics.error(... traceback ...) for that same failure.
Target invariant: 1 worker failure → 1 QUANT_ISIN_PROCESSED FAILED event → real worker traceback inside ErrorDetails.

Remove the config → infrastructure dependency inversion
File: src/personal_finance_etl/config/settings.py
Remove the direct dependency on infrastructure.preferences.PreferencesManager and specifically the preference-persistence side effect from Settings. Settings should own configuration validation/state only. Move the add_recent_config(...) orchestration to the appropriate application/bootstrap/presentation caller that already coordinates configuration selection.
Also strengthen tests/test_architecture_boundaries.py so config is explicitly forbidden from importing infrastructure, preventing regression.

Finish the module ownership rubric
Files:
src/personal_finance_etl/contracts/event_transport.py
src/personal_finance_etl/infrastructure/warehouse/schema/control_plane.py
Add proper module-level Owns / Does not own sections consistent with your engineering standards. For event_transport.py, make clear it owns the typed event-transport boundary, not emission/sink/presentation behavior. For control_plane.py, keep its existing ownership statement and explicitly state what schema definitions do not own, especially connection lifecycle, repository behavior, migrations/orchestration, or operational business logic.
