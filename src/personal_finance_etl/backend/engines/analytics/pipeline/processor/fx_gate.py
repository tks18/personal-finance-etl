"""FX rate validation gate for the per-ISIN analytics pipeline.

The :class:`FXValidationGate` performs a pre-flight check before the main
market-data loop: it warns when a foreign-currency instrument has no FX
provider or when the provider cannot supply a rate for the first purchase date.

Separating this from :class:`IsinProcessor` keeps each class focused and makes
the validation independently testable.
"""

from datetime import date
from typing import Any

from personal_finance_etl.backend.utils.logger import logger


class FXValidationGate:
    """Pre-Quant FX provider availability check for a single ISIN.

    Parameters
    ----------
    rules:
        Financial rules instance; used to resolve the default currency ID.
    fx_provider:
        Optional FX rate provider.  When ``None`` and the instrument is in a
        foreign currency, a warning is emitted.
    """

    def __init__(self, rules: Any, fx_provider: Any):
        self.rules = rules
        self.fx_provider = fx_provider
        self._default_currency: str = getattr(rules, "DEFAULT_CURRENCY_ID", "INR_INR")

    def validate(self, isin: str, master_row: dict[str, Any], first_p_date: date) -> None:
        """Emit structured warnings when FX data is unavailable for *isin*.

        Parameters
        ----------
        isin:
            The instrument identifier (used in log messages).
        master_row:
            Master-data dict for this ISIN; must contain ``CURRENCY_ID``.
        first_p_date:
            Date of the earliest purchase.  Used as the spot-check date.

        Notes
        -----
        This method only emits warnings — it does not raise.  Downstream
        callers continue processing; the warnings surface data-quality issues
        without aborting the run.
        """
        instrument_currency = master_row.get("CURRENCY_ID", "") or ""
        is_foreign = bool(instrument_currency) and instrument_currency != self._default_currency

        if not is_foreign:
            return  # Base-currency instruments never need FX validation

        if not self.fx_provider:
            logger.warning(
                f"[FX:WARN] ISIN={isin} is denominated in {instrument_currency} but no FX provider "
                "is configured. All base-currency valuations will be computed at FX_Rate=1.0 "
                "(identity), producing incorrect INR values."
            )
            return

        # Spot-check: verify at least one rate is available for the first purchase date.
        spot_rate = self.fx_provider.get_rate(first_p_date, instrument_currency)
        if spot_rate is None or spot_rate <= 0:
            logger.warning(
                f"[FX:WARN] ISIN={isin} ({instrument_currency}): FX provider returned no rate "
                f"for {first_p_date}. Values from this date onward may be computed at "
                "FX_Rate=NaN, producing incorrect INR values."
            )
