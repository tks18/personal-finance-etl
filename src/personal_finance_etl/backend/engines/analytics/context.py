"""Legacy delegation shim for analytics context manager.

Superseded by personal_finance_etl.application.investments.context.
"""

from personal_finance_etl.application.investments.context import (
    AnalyticsContextManager as AnalyticsContextManager,
)

__all__ = ["AnalyticsContextManager"]
