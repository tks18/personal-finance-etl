"""Legacy delegation shim for ISIN data extractor.

Superseded by personal_finance_etl.application.investments.input_adapter.
"""

from personal_finance_etl.application.investments.input_adapter import (
    IsinDataExtractor as IsinDataExtractor,
)

__all__ = ["IsinDataExtractor"]
