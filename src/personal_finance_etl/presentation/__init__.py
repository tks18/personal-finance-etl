"""Human-facing presentation surfaces: CLI, Desktop GUI, and Documentation browser.

Owns
----
- CLI commands and argument parsing.
- Desktop GUI (CustomTkinter) application, views, base tabs, and theme configuration.
- Packaged documentation browser and markdown renderer.
- Human-facing application launcher.

Does not own
-------------
- Financial calculations, rules, or domain models (owned by domain.*).
- Execution orchestration (owned by application.*).
- Storage or persistence mechanisms (owned by infrastructure.*).
"""
