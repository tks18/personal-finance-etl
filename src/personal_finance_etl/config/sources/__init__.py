"""Physical evidence source configuration package.

Owns
----
- SourceConfig: Declarative validated evidence source configuration model.

Does not own
------------
- SourceId and ProviderType contract definitions (owned by contracts.sources).
- Root settings or runtime operational environment flags (owned by config.settings).
"""

from __future__ import annotations

from personal_finance_etl.config.sources.model import SourceConfig

__all__ = ["SourceConfig"]
