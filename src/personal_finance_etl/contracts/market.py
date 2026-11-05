"""Provider-neutral market vocabulary and external symbol mapping contracts.

Owns
----
- ProviderSymbolMapping: Explicit mapping from canonical financial identity to external vendor symbol.
- ProviderSymbolRegistry: Immutable in-memory registry resolving canonical identities to provider symbols.

Does not own
-------------
- HTTP or API provider implementations (owned by infrastructure.providers.market).
- Currency conversion or continuous benchmark logic (owned by domain.market).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProviderSymbolMapping:
    """Explicit mapping from a canonical financial identity to an external vendor symbol.

    Parameters
    ----------
    canonical_id : str
        Canonical security/currency/benchmark identity (e.g. ISIN "US0378331005",
        Currency "USD", Benchmark ID "NIFTY50").
    provider_symbol : str
        Provider-specific query ticker/symbol (e.g. "AAPL", "USDINR=X", "^NSEI").
    provider_id : str, default "YahooFinance"
        Market data provider identifier.
    target_currency_code : str | None, default None
        Optional target settlement currency for FX pairs (e.g. "INR").
    """

    canonical_id: str
    provider_symbol: str
    provider_id: str = "YahooFinance"
    target_currency_code: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderSymbolRegistry(Mapping[str, str]):
    """Immutable in-memory registry of provider-specific market symbols.

    Provides O(1) symbol lookup by (provider_id, canonical_id) or
    (provider_id, canonical_id, target_currency).
    """

    mappings: Mapping[tuple[str, str], str] = field(
        default_factory=lambda: dict[tuple[str, str], str]()
    )
    fx_mappings: Mapping[tuple[str, str, str], str] = field(
        default_factory=lambda: dict[tuple[str, str, str], str]()
    )

    def get_symbol(self, canonical_id: str, provider_id: str = "YahooFinance") -> str | None:
        """Resolve external vendor symbol for a canonical security or benchmark identifier.

        Parameters
        ----------
        canonical_id : str
            Canonical entity identifier (ISIN, Benchmark ID, etc.).
        provider_id : str, default "YahooFinance"
            Market provider identifier.

        Returns
        -------
        str | None
            Provider-specific query symbol if registered, None otherwise.
        """
        return self.mappings.get((provider_id, canonical_id))

    def get_fx_symbol(
        self,
        base_currency: str,
        target_currency: str,
        provider_id: str = "YahooFinance",
    ) -> str | None:
        """Resolve external vendor symbol for a currency exchange rate pair.

        Parameters
        ----------
        base_currency : str
            Source currency ISO/UID (e.g. "USD").
        target_currency : str
            Target currency ISO/UID (e.g. "INR").
        provider_id : str, default "YahooFinance"
            Market provider identifier.

        Returns
        -------
        str | None
            Provider-specific FX pair symbol if registered, None otherwise.
        """
        direct = self.fx_mappings.get((provider_id, base_currency, target_currency))
        if direct is not None:
            return direct
        return self.mappings.get((provider_id, base_currency))

    def __getitem__(self, canonical_id: str) -> str:
        """Resolve external vendor symbol for a canonical security or benchmark identifier.

        Parameters
        ----------
        canonical_id : str
            Canonical entity identifier.

        Returns
        -------
        str
            Provider symbol.

        Raises
        ------
        KeyError
            If canonical_id is not registered under the default provider.
        """
        sym = self.get_symbol(canonical_id)
        if sym is None:
            raise KeyError(canonical_id)
        return sym

    def __contains__(self, key: object) -> bool:
        """Check presence of canonical identifier in registry under default provider.

        Parameters
        ----------
        key : object
            Canonical identifier string or (provider_id, canonical_id) tuple.

        Returns
        -------
        bool
            True if present, False otherwise.
        """
        if isinstance(key, tuple):
            return key in self.mappings
        if isinstance(key, str):
            return ("YahooFinance", key) in self.mappings
        return False

    def __iter__(self) -> Iterator[str]:
        """Iterate over canonical identifiers registered under the default provider.

        Returns
        -------
        Iterator[str]
            Iterator yielding canonical entity IDs.
        """
        for pid, cid in self.mappings:
            if pid == "YahooFinance":
                yield cid

    def __len__(self) -> int:
        """Return count of canonical identifiers registered under the default provider.

        Returns
        -------
        int
            Number of registered symbols.
        """
        return sum(1 for pid, _ in self.mappings if pid == "YahooFinance")

    def get_symbol_map(self, provider_id: str = "YahooFinance") -> dict[str, str]:
        """Return dictionary mapping canonical_id -> provider_symbol for a provider.

        Parameters
        ----------
        provider_id : str, default "YahooFinance"
            Market provider identifier.

        Returns
        -------
        dict[str, str]
            Dictionary of canonical identifiers to provider symbols.
        """
        return {cid: sym for (pid, cid), sym in self.mappings.items() if pid == provider_id}

    @classmethod
    def from_mappings(cls, mappings: Sequence[ProviderSymbolMapping]) -> ProviderSymbolRegistry:
        """Construct registry from a sequence of ProviderSymbolMapping records.

        Parameters
        ----------
        mappings : Sequence[ProviderSymbolMapping]
            Sequence of provider symbol mapping definitions.

        Returns
        -------
        ProviderSymbolRegistry
            Populated immutable registry.
        """
        by_id: dict[tuple[str, str], str] = {}
        by_fx: dict[tuple[str, str, str], str] = {}
        for m in mappings:
            by_id[(m.provider_id, m.canonical_id)] = m.provider_symbol
            if m.target_currency_code:
                by_fx[(m.provider_id, m.canonical_id, m.target_currency_code)] = m.provider_symbol
        return cls(mappings=by_id, fx_mappings=by_fx)
