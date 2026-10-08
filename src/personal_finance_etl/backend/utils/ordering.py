from typing import Any


def sort_purchases(purchases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sorts a list of purchases according to the unified same-day rule:
    Date ASC, Price ASC, Purchase_ID ASC.
    """
    return sorted(
        purchases,
        key=lambda x: (
            x.get("Date"),
            float(x.get("Price", x.get("Buy_Price_Local", 0.0))),
            str(x.get("Purchase_ID", "")),
        ),
    )


def sort_sales(sales: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sorts a list of sales according to the unified same-day rule:
    Date ASC, Sell_Price ASC, Sale_ID ASC.
    """
    return sorted(
        sales,
        key=lambda x: (
            x.get("Date"),
            float(x.get("Sell_Price", x.get("Price", 0.0))),
            str(x.get("Sale_ID", "")),
        ),
    )

