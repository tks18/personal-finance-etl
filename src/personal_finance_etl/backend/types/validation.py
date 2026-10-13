from typing import Any


class FinancialSourceValidationError(ValueError):
    """Raised when a populated source value fails strict financial parsing.

    Distinguishes malformed inputs (which must fail loudly to avoid silent data
    corruption) from absent optional fields (which resolve to valid nulls).
    """

    def __init__(
        self,
        message: str,
        *,
        source: str | None = None,
        sheet: str | None = None,
        field_name: str | None = None,
        raw_value: Any = None,
        row_identifier: Any = None,
    ) -> None:
        context_parts: list[str] = []
        if source:
            context_parts.append(f"source={source}")
        if sheet:
            context_parts.append(f"sheet={sheet}")
        if field_name:
            context_parts.append(f"field={field_name}")
        if raw_value is not None:
            context_parts.append(f"raw_value={raw_value!r}")
        if row_identifier is not None:
            context_parts.append(f"row={row_identifier}")
        ctx_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        super().__init__(f"{message}{ctx_str}")
        self.source = source
        self.sheet = sheet
        self.field_name = field_name
        self.raw_value = raw_value
        self.row_identifier = row_identifier

