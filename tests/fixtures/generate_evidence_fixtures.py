"""Utility script to generate canonical static evidence fixtures for PFETL tests.

Owns:
- Generation of binary-valid Excel (.xlsx), SQLite (.sqlite), and CSV (.csv) fixtures.
- Deterministic fixture generation in tests/fixtures/evidence/.
"""

import io
import shutil
import sqlite3
import zipfile
from datetime import date, datetime
from pathlib import Path


def _build_xlsx(sheet_name: str, rows: list[list[object]]) -> bytes:
    """Build a minimal valid .xlsx binary payload using standard library zipfile.

    Parameters
    ----------
    sheet_name : str
        Target worksheet title.
    rows : list[list[object]]
        Table rows including header row.

    Returns
    -------
    bytes
        Valid raw Excel workbook byte stream.
    """
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    wb = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )

    ws_rows: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, val in enumerate(row):
            # Calculate column letters (A, B, ..., Z, AA, AB, ...)
            c_num = c_idx
            letters = ""
            while c_num >= 0:
                letters = chr(65 + (c_num % 26)) + letters
                c_num = (c_num // 26) - 1
            cell_ref = f"{letters}{r_idx}"

            if val is None:
                continue
            if isinstance(val, (int, float)):
                cells.append(f'<c r="{cell_ref}"><v>{val}</v></c>')
            elif isinstance(val, (datetime, date)):
                iso_str = val.isoformat()
                cells.append(f'<c r="{cell_ref}" t="d"><v>{iso_str}</v></c>')
            else:
                str_val = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{str_val}</t></is></c>')
        row_str = f'<row r="{r_idx}">{"".join(cells)}</row>'
        ws_rows.append(row_str)

    ws = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(ws_rows)}</sheetData>"
        "</worksheet>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/worksheets/sheet1.xml", ws)

    return buf.getvalue()


def build_household_evidence(base_dir: Path) -> Path:
    """Build canonical SQLite household database fixture."""
    hh_dir = base_dir / "household"
    hh_dir.mkdir(parents=True, exist_ok=True)
    db_path = hh_dir / "SOURCE_DB.sqlite"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE ZCATEGORY (
                ID INTEGER PRIMARY KEY,
                C_IS_DEL INTEGER,
                C_UTIME INTEGER,
                uid TEXT UNIQUE,
                NAME TEXT NOT NULL,
                ORDERSEQ INTEGER,
                TYPE INTEGER NOT NULL,
                STATUS INTEGER,
                pUid TEXT,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        zcat_rows = [
            (
                1,
                0,
                1700000000,
                "CAT_INCOME_SALARY",
                "Income from Salary",
                1,
                0,
                0,
                None,
                1,
                1700000000.0,
                1,
            ),
            (
                2,
                0,
                1700000000,
                "SUBCAT_INCOME_BONUS",
                "Annual Bonus",
                2,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                3,
                0,
                1700000000,
                "CAT_EXPENSE_FOOD",
                "Food & Groceries",
                3,
                1,
                0,
                None,
                1,
                1700000000.0,
                1,
            ),
            (
                4,
                0,
                1700000000,
                "SUBCAT_EXPENSE_DINING",
                "Restaurant Dining",
                4,
                1,
                0,
                "CAT_EXPENSE_FOOD",
                1,
                1700000000.0,
                1,
            ),
            (
                5,
                0,
                1700000000,
                "CAT_EXPENSE_RENT",
                "Housing & Rent",
                5,
                1,
                0,
                None,
                1,
                1700000000.0,
                1,
            ),
            (
                6,
                0,
                1700000000,
                "CAT_INVEST_MF",
                "Mutual Funds Investment",
                6,
                1,
                0,
                None,
                1,
                1700000000.0,
                1,
            ),
            (
                7,
                0,
                1700000000,
                "64E7E571-6524-4A1D-BAE6-C68F751BB79D",
                "Stocks LTCG",
                7,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                8,
                0,
                1700000000,
                "45E5EAEC-1A70-48C7-8707-F1CCB3555607",
                "Mutual Fund LTCG",
                8,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                9,
                0,
                1700000000,
                "492CCDAA-4C8E-4A7A-88AA-052CF75D4325",
                "ETF LTCG",
                9,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                10,
                0,
                1700000000,
                "602cad79-9d08-46f5-a019-7653979f453b",
                "ETF STCG",
                10,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                11,
                0,
                1700000000,
                "8fdf821a-209f-4633-9f3c-ec2d8c32c115",
                "Mutual Fund STCG",
                11,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                12,
                0,
                1700000000,
                "445a3173-250a-4d0f-a32b-2383f3dc82d5",
                "Stocks STCG",
                12,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                13,
                0,
                1700000000,
                "SUBCAT_EXPENSE_RENT",
                "Monthly Rent",
                13,
                1,
                0,
                "CAT_EXPENSE_RENT",
                1,
                1700000000.0,
                1,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO ZCATEGORY (
                ID, C_IS_DEL, C_UTIME, uid, NAME, ORDERSEQ, TYPE, STATUS, pUid, isSynced, syncTime, syncVersion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            zcat_rows,
        )

        conn.execute(
            """
            CREATE TABLE ASSETGROUP (
                ID INTEGER PRIMARY KEY,
                DEVICE_ID INTEGER,
                uid TEXT UNIQUE,
                IS_DEL INTEGER,
                USETIME INTEGER,
                ACC_GROUP_NAME TEXT NOT NULL,
                TYPE INTEGER NOT NULL,
                ORDERSEQ INTEGER,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        ag_rows = [
            (1, 101, "AG_BANK", 0, 1700000000, "Bank Accounts", 0, 1, 1, 1700000000.0, 1),
            (2, 101, "AG_INVEST", 0, 1700000000, "Investment Portfolios", 1, 2, 1, 1700000000.0, 1),
            (3, 101, "AG_CASH", 0, 1700000000, "Cash & Equivalents", 0, 3, 1, 1700000000.0, 1),
        ]
        conn.executemany(
            """
            INSERT INTO ASSETGROUP (
                ID, DEVICE_ID, uid, IS_DEL, USETIME, ACC_GROUP_NAME, TYPE, ORDERSEQ, isSynced, syncTime, syncVersion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ag_rows,
        )

        conn.execute(
            """
            CREATE TABLE ASSETS (
                ID INTEGER PRIMARY KEY,
                CARD_DAY_FIN TEXT,
                CARD_DAY_PAY TEXT,
                NIC_NAME TEXT NOT NULL,
                ORDERSEQ INTEGER,
                ZDATA TEXT,
                ZDATA1 TEXT,
                ZDATA2 TEXT,
                IS_TRANS_EXPENSE INTEGER,
                IS_CARD_AUTO_PAY INTEGER,
                APP_PACKAGE TEXT,
                APP_NAME TEXT,
                SMS_TEL TEXT,
                SMS_STRING TEXT,
                A_UTIME INTEGER,
                CARD_USAGE_HURDLE_TYPE INTEGER,
                CARD_USAGE_HURDLE_START_DATE REAL,
                CARD_USAGE_HURDLE_AMOUNT REAL,
                uid TEXT UNIQUE,
                currencyUid TEXT,
                cardAssetUid TEXT,
                groupUid TEXT,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        asset_rows = [
            (
                1,
                "0",
                "0",
                "HDFC Salary",
                1,
                "0",
                "Main checking account",
                "Notes",
                0,
                0,
                "com.hdfc",
                "HDFC Bank",
                "HDFCBK",
                "sms",
                1700000000,
                0,
                0.0,
                0.0,
                "ASSET_HDFC",
                "CURR_INR",
                None,
                "AG_BANK",
                1,
                1700000000.0,
                1,
            ),
            (
                2,
                "0",
                "0",
                "Zerodha Trading",
                2,
                "0",
                "Equity & MF Demat",
                "Notes",
                0,
                0,
                "com.zerodha",
                "Zerodha",
                "ZERODH",
                "sms",
                1700000000,
                0,
                0.0,
                0.0,
                "ASSET_ZERODHA",
                "CURR_INR",
                None,
                "AG_INVEST",
                1,
                1700000000.0,
                1,
            ),
            (
                3,
                "0",
                "0",
                "Wallet Cash",
                3,
                "0",
                "Physical cash in hand",
                "Notes",
                0,
                0,
                "com.wallet",
                "Cash",
                "CASH",
                "sms",
                1700000000,
                0,
                0.0,
                0.0,
                "ASSET_CASH",
                "CURR_INR",
                None,
                "AG_CASH",
                1,
                1700000000.0,
                1,
            ),
            (
                4,
                "0",
                "0",
                "Mutual Funds",
                4,
                "0",
                "Mutual Funds Holdings",
                "Notes",
                0,
                0,
                "com.mf",
                "Mutual Funds",
                "MF",
                "sms",
                1700000000,
                0,
                0.0,
                0.0,
                "ASSET_MF",
                "CURR_INR",
                None,
                "AG_INVEST",
                1,
                1700000000.0,
                1,
            ),
            (
                5,
                "0",
                "0",
                "Stocks & ETFs",
                5,
                "0",
                "Domestic and US Equities",
                "Notes",
                0,
                0,
                "com.stocks",
                "Stocks & ETFs",
                "STOCKS",
                "sms",
                1700000000,
                0,
                0.0,
                0.0,
                "ASSET_STOCKS",
                "CURR_INR",
                None,
                "AG_INVEST",
                1,
                1700000000.0,
                1,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO ASSETS (
                ID, CARD_DAY_FIN, CARD_DAY_PAY, NIC_NAME, ORDERSEQ, ZDATA, ZDATA1, ZDATA2,
                IS_TRANS_EXPENSE, IS_CARD_AUTO_PAY, APP_PACKAGE, APP_NAME, SMS_TEL, SMS_STRING,
                A_UTIME, CARD_USAGE_HURDLE_TYPE, CARD_USAGE_HURDLE_START_DATE, CARD_USAGE_HURDLE_AMOUNT,
                uid, currencyUid, cardAssetUid, groupUid, isSynced, syncTime, syncVersion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            asset_rows,
        )

        conn.execute(
            """
            CREATE TABLE CURRENCY (
                ID INTEGER PRIMARY KEY,
                uid TEXT UNIQUE,
                NAME TEXT NOT NULL,
                ISO TEXT,
                MAIN_ISO TEXT,
                IS_DEL INTEGER,
                ORDER_SEQ INTEGER,
                RATE REAL,
                SYMBOL TEXT,
                INSERT_TYPE TEXT,
                SYMBOL_POSITION TEXT,
                IS_MAIN_CURRENCY INTEGER,
                IS_SHOW INTEGER,
                MODIFY_DATE INTEGER,
                DECIMAL_POINT INTEGER,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        curr_rows = [
            (
                1,
                "INR_INR",
                "Indian Rupee",
                "INR",
                "INR",
                0,
                1,
                1.0,
                "₹",
                "0",
                "0",
                1,
                1,
                1700000000,
                2,
                1,
                1700000000.0,
                1,
            ),
            (
                2,
                "CURR_INR",
                "Indian Rupee",
                "INR",
                "INR",
                0,
                1,
                1.0,
                "₹",
                "0",
                "0",
                1,
                1,
                1700000000,
                2,
                1,
                1700000000.0,
                1,
            ),
            (
                3,
                "USD",
                "US Dollar",
                "USD",
                "USD",
                0,
                2,
                83.0,
                "$",
                "0",
                "0",
                0,
                1,
                1700000000,
                2,
                1,
                1700000000.0,
                1,
            ),
            (
                4,
                "CURR_USD",
                "US Dollar",
                "USD",
                "USD",
                0,
                2,
                83.0,
                "$",
                "0",
                "0",
                0,
                1,
                1700000000,
                2,
                1,
                1700000000.0,
                1,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO CURRENCY (
                ID, uid, NAME, ISO, MAIN_ISO, IS_DEL, ORDER_SEQ, RATE, SYMBOL,
                INSERT_TYPE, SYMBOL_POSITION, IS_MAIN_CURRENCY, IS_SHOW, MODIFY_DATE,
                DECIMAL_POINT, isSynced, syncTime, syncVersion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            curr_rows,
        )

        conn.execute(
            """
            CREATE TABLE INOUTCOME (
                AID INTEGER PRIMARY KEY,
                uid TEXT UNIQUE,
                assetUid TEXT NOT NULL,
                CARDDIVIDMONTH TEXT,
                ctgUid TEXT,
                toAssetUid TEXT,
                ZCONTENT TEXT,
                ZDATE TEXT NOT NULL,
                WDATE TEXT,
                wtime TEXT,
                paid TEXT,
                DO_TYPE TEXT NOT NULL,
                ZMONEY TEXT NOT NULL,
                txUidTrans TEXT,
                ZDATA TEXT,
                SMS_RDATE TEXT,
                IN_ZMONEY TEXT,
                ASSET_NIC TEXT,
                CATEGORY_NAME TEXT,
                cardDivideUid TEXT,
                CARD_DIVIDE_MONTH_STR TEXT,
                MARK INTEGER,
                txUidFee TEXT,
                SMS_ORIGIN TEXT,
                SMS_PARSE_CONTENT TEXT,
                IS_DEL INTEGER,
                UTIME INTEGER,
                currencyUid TEXT,
                AMOUNT_ACCOUNT REAL,
                lat REAL,
                lng REAL,
                gstd TEXT,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        tx_rows = [
            (
                1,
                "TX_001",
                "ASSET_HDFC",
                "0",
                "SUBCAT_INCOME_BONUS",
                None,
                "Monthly Salary",
                "1700000000",
                "2023-11-15",
                "10:00:00",
                "1",
                "0",
                "75000.0",
                None,
                "Memo",
                "2023-11-15",
                "75000.0",
                "HDFC Salary",
                "Income from Salary",
                None,
                None,
                0,
                None,
                "HDFCBK",
                "salary credited",
                0,
                1700000000,
                "CURR_INR",
                75000.0,
                0.0,
                0.0,
                "IN",
                1,
                1700000000.0,
                1,
            ),
            (
                2,
                "TX_002",
                "ASSET_HDFC",
                "0",
                "SUBCAT_EXPENSE_DINING",
                None,
                "Supermarket Groceries",
                "1700100000",
                "2023-11-16",
                "18:30:00",
                "1",
                "1",
                "2500.0",
                None,
                "Groceries",
                "2023-11-16",
                "2500.0",
                "HDFC Salary",
                "Food & Groceries",
                None,
                None,
                0,
                None,
                "HDFCBK",
                "pos transaction",
                0,
                1700100000,
                "CURR_INR",
                2500.0,
                0.0,
                0.0,
                "IN",
                1,
                1700100000.0,
                1,
            ),
            (
                3,
                "TX_003",
                "ASSET_HDFC",
                "0",
                "SUBCAT_EXPENSE_RENT",
                None,
                "Monthly House Rent",
                "1701400000",
                "2023-12-01",
                "09:00:00",
                "1",
                "1",
                "20000.0",
                None,
                "Rent",
                "2023-12-01",
                "20000.0",
                "HDFC Salary",
                "Housing & Rent",
                None,
                None,
                0,
                None,
                "HDFCBK",
                "neft transfer",
                0,
                1701400000,
                "CURR_INR",
                20000.0,
                0.0,
                0.0,
                "IN",
                1,
                1701400000.0,
                1,
            ),
            (
                4,
                "TX_004",
                "ASSET_HDFC",
                "0",
                None,
                "ASSET_ZERODHA",
                "Fund Transfer to Broker",
                "1701500000",
                "2023-12-02",
                "11:00:00",
                "1",
                "2",
                "30000.0",
                "TX_004_T",
                "Transfer",
                "2023-12-02",
                "30000.0",
                "HDFC Salary",
                "Transfer",
                None,
                None,
                0,
                None,
                "HDFCBK",
                "upi transfer",
                0,
                1701500000,
                "CURR_INR",
                30000.0,
                0.0,
                0.0,
                "IN",
                1,
                1701500000.0,
                1,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO INOUTCOME (
                AID, uid, assetUid, CARDDIVIDMONTH, ctgUid, toAssetUid, ZCONTENT,
                ZDATE, WDATE, wtime, paid, DO_TYPE, ZMONEY, txUidTrans, ZDATA,
                SMS_RDATE, IN_ZMONEY, ASSET_NIC, CATEGORY_NAME, cardDivideUid,
                CARD_DIVIDE_MONTH_STR, MARK, txUidFee, SMS_ORIGIN, SMS_PARSE_CONTENT,
                IS_DEL, UTIME, currencyUid, AMOUNT_ACCOUNT, lat, lng, gstd,
                isSynced, syncTime, syncVersion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tx_rows,
        )
        conn.commit()
    finally:
        conn.close()

    return db_path


def build_mf_evidence(base_dir: Path) -> dict[str, Path]:
    """Build canonical mutual fund Excel evidence files."""
    holdings_dir = base_dir / "mutual_funds" / "Mutual Funds - Holdings"
    orders_dir = base_dir / "mutual_funds" / "Mutual Funds - Orders"
    holdings_dir.mkdir(parents=True, exist_ok=True)
    orders_dir.mkdir(parents=True, exist_ok=True)

    holdings_rows: list[list[object]] = [
        ["Groww Mutual Fund Portfolio Report", "", "", "", "", "", "", "", "", "", ""],
        ["Investor: Shan", "", "", "", "", "", "", "", "", "", ""],
        ["Generated on: 31-03-2024", "", "", "", "", "", "", "", "", "", ""],
        [
            "Scheme Name",
            "AMC",
            "Category",
            "Sub-category",
            "Folio No.",
            "Source",
            "Units",
            "Invested Value",
            "Current Value",
            "Returns",
            "XIRR",
        ],
        [
            "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
            "PPFAS Mutual Fund",
            "Equity",
            "Flexi Cap",
            "12345/01",
            "Kuvera",
            100.5,
            50000.0,
            65000.0,
            15000.0,
            18.5,
        ],
        [
            "Mirae Asset Large Cap Fund - Direct Plan - Growth",
            "Mirae Asset Mutual Fund",
            "Equity",
            "Large Cap",
            "67890/02",
            "Kuvera",
            200.0,
            80000.0,
            95000.0,
            15000.0,
            14.2,
        ],
    ]
    holdings_path = holdings_dir / "mf_holdings_31-03-2024.xlsx"
    holdings_path.write_bytes(_build_xlsx("Holdings", holdings_rows))

    orders_rows: list[list[object]] = [
        ["Groww Order History", "", "", "", "", ""],
        ["Account: Shan", "", "", "", "", ""],
        ["Scheme Name", "Transaction Type", "Units", "NAV", "Amount", "Date"],
        [
            "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
            "PURCHASE",
            100.5,
            497.51,
            50000.0,
            "15-Jan-2023",
        ],
        [
            "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
            "REDEEM",
            10.5,
            550.0,
            5775.0,
            "20-Feb-2024",
        ],
    ]
    orders_path = orders_dir / "mf_orders_31-03-2024.xlsx"
    orders_path.write_bytes(_build_xlsx("Transactions", orders_rows))

    neg_dir = base_dir / "negative"
    neg_dir.mkdir(parents=True, exist_ok=True)

    corrupt_orders_rows: list[list[object]] = [
        ["Scheme Name", "Units", "Amount"],
        ["Parag Parikh Flexi Cap Fund", 100.0, 50000.0],
    ]
    corrupt_orders_path = neg_dir / "mf_orders_corrupt.xlsx"
    corrupt_orders_path.write_bytes(_build_xlsx("Transactions", corrupt_orders_rows))

    return {
        "mf_holdings": holdings_path,
        "mf_orders": orders_path,
        "mf_orders_corrupt": corrupt_orders_path,
    }


def build_stock_evidence(base_dir: Path) -> dict[str, Path]:
    """Build canonical domestic stock Excel evidence files."""
    pl_dir = base_dir / "domestic_stocks" / "Stock PL Statements"
    orders_dir = base_dir / "domestic_stocks" / "Stock - Orders"
    pl_dir.mkdir(parents=True, exist_ok=True)
    orders_dir.mkdir(parents=True, exist_ok=True)
    neg_dir = base_dir / "negative"
    neg_dir.mkdir(parents=True, exist_ok=True)

    pl_rows: list[list[object]] = [
        ["Portfolio Profit and Loss Report"],
        ["Unrealised trades"],
        ["Detailed Stock Valuation Breakdown"],
        [
            "Stock name",
            "ISIN",
            "Quantity",
            "Buy date",
            "Buy price",
            "Buy value",
            "Closing date",
            "Closing price",
            "Closing value",
            "Unrealised P&L",
            "Remark",
        ],
        [
            "RELIANCE IND",
            "INE002A01018",
            10,
            "15-01-2023",
            2400.0,
            24000.0,
            "31-03-2024",
            2900.0,
            29000.0,
            5000.0,
            "Long Term",
        ],
        [
            "INFOSYS LTD",
            "INE009A01021",
            20,
            "10-02-2023",
            1500.0,
            30000.0,
            "31-03-2024",
            1600.0,
            32000.0,
            2000.0,
            "Long Term",
        ],
    ]
    pl_path = pl_dir / "stock_pl_31-03-2024.xlsx"
    pl_path.write_bytes(_build_xlsx("Trade Level", pl_rows))

    orders_rows: list[list[object]] = [
        ["Name", "Thirumazhisai Kannan Sudharshan"],
        ["Unique Client Code", "6353187399"],
        [None],
        ["Order history for stocks from 01-04-2023 to 31-03-2024"],
        [None],
        [
            "Stock name",
            "Symbol",
            "ISIN",
            "Type",
            "Quantity",
            "Value",
            "Exchange",
            "Exchange Order Id",
            "Execution date and time",
            "Order status",
        ],
        [
            "RELIANCE IND",
            "RELIANCE",
            "INE002A01018",
            "BUY",
            10,
            24000.0,
            "NSE",
            "1100000000000001",
            "15-01-2023 10:30 AM",
            "Executed",
        ],
        [
            "INFOSYS LTD",
            "INFY",
            "INE009A01021",
            "BUY",
            20,
            30000.0,
            "NSE",
            "1100000000000002",
            "10-02-2023 11:15 AM",
            "Executed",
        ],
        [
            "INFOSYS LTD",
            "INFY",
            "INE009A01021",
            "SELL",
            5,
            8000.0,
            "NSE",
            "1100000000000003",
            "15-03-2024 02:00 PM",
            "Executed",
        ],
    ]
    orders_path = orders_dir / "stock_orders_31-03-2024.xlsx"
    orders_path.write_bytes(_build_xlsx("Sheet1", orders_rows))

    empty_orders_rows: list[list[object]] = [
        ["Name", "Thirumazhisai Kannan Sudharshan"],
        ["Unique Client Code", "6353187399"],
        [None],
        ["Order history for stocks from 01-04-2023 to 31-03-2024"],
        [None],
        [
            "Stock name",
            "Symbol",
            "ISIN",
            "Type",
            "Quantity",
            "Value",
            "Exchange",
            "Exchange Order Id",
            "Execution date and time",
            "Order status",
        ],
    ]
    empty_orders_path = neg_dir / "stock_orders_empty_31-03-2024.xlsx"
    empty_orders_path.write_bytes(_build_xlsx("Sheet1", empty_orders_rows))

    corrupt_pl_rows: list[list[object]] = [
        ["Portfolio Profit and Loss Report"],
        ["Unrealised trades"],
        ["Detailed Stock Valuation Breakdown"],
        ["Stock name", "ISIN", "Buy date"],  # Missing mandatory 'Quantity' column
        ["RELIANCE IND", "INE002A01018", "15-01-2023"],
    ]
    corrupt_pl_path = neg_dir / "stock_pl_corrupt.xlsx"
    corrupt_pl_path.write_bytes(_build_xlsx("Trade Level", corrupt_pl_rows))

    return {
        "stock_pl": pl_path,
        "stock_pl_corrupt": corrupt_pl_path,
        "stock_orders": orders_path,
        "stock_orders_empty": empty_orders_path,
    }


def build_us_stock_evidence(base_dir: Path) -> dict[str, Path]:
    """Build canonical US stock Excel evidence files."""
    reports_dir = (
        base_dir / "us_stocks" / "IND Money (US Stocks)" / "Transaction Reports" / "2025-26"
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    neg_dir = base_dir / "negative"
    neg_dir.mkdir(parents=True, exist_ok=True)

    tx_rows: list[list[object]] = [
        [
            "Stock Name",
            "ISIN",
            "Stock Symbol",
            "Yahoo Ticker",
            "Order Date",
            "Currency",
            "Transaction Type",
            "Order Type",
            "Quantity",
            "Price ($)",
            "Order Amount ($)",
            "Brokerage ($)",
            "Exch Rate",
            "Order Amount (INR)",
            "Brokerage (INR)",
        ],
        [
            "Apple Inc.",
            "US0378331005",
            "AAPL",
            "AAPL",
            datetime(2024, 1, 15, 14, 30, 0),
            "USD",
            "BUY",
            "MARKET",
            2.5,
            180.0,
            450.0,
            0.0,
            83.0,
            37350.0,
            0.0,
        ],
        [
            "Apple Inc.",
            "US0378331005",
            "AAPL",
            "AAPL",
            datetime(2024, 4, 15, 15, 45, 0),
            "USD",
            "SELL",
            "LIMIT",
            1.0,
            190.0,
            190.0,
            0.0,
            83.5,
            15865.0,
            0.0,
        ],
    ]
    tx_path = reports_dir / "02-2026.xlsx"
    tx_path.write_bytes(_build_xlsx("02-2026", tx_rows))

    malformed_rows: list[list[object]] = [
        [
            "ISIN",
            "Stock Symbol",
            "Yahoo Ticker",
            "Order Date",
            "Currency",
            "Transaction Type",
            "Order Type",
            "Quantity",
        ],
        [
            "US0378331005",
            "AAPL",
            "AAPL",
            datetime(2024, 1, 15, 14, 30, 0),
            "USD",
            "BUY",
            "MARKET",
            2.5,
        ],
    ]
    malformed_path = neg_dir / "us_trades_malformed.xlsx"
    malformed_path.write_bytes(_build_xlsx("02-2026", malformed_rows))

    null_isin_rows: list[list[object]] = [
        [
            "Stock Name",
            "ISIN",
            "Stock Symbol",
            "Yahoo Ticker",
            "Order Date",
            "Currency",
            "Transaction Type",
            "Order Type",
            "Quantity",
            "Price ($)",
            "Order Amount ($)",
            "Brokerage ($)",
            "Exch Rate",
            "Order Amount (INR)",
            "Brokerage (INR)",
        ],
        [
            "Apple Inc.",
            None,
            "AAPL",
            "AAPL",
            datetime(2024, 1, 15, 14, 30, 0),
            "USD",
            "BUY",
            "MARKET",
            2.5,
            180.0,
            450.0,
            0.0,
            83.0,
            37350.0,
            0.0,
        ],
    ]
    null_isin_path = neg_dir / "us_trades_null_isin.xlsx"
    null_isin_path.write_bytes(_build_xlsx("02-2026", null_isin_rows))

    return {
        "us_stock_transactions": tx_path,
        "us_trades_malformed": malformed_path,
        "us_trades_null_isin": null_isin_path,
    }


def build_reference_evidence(base_dir: Path) -> dict[str, Path]:
    """Build canonical reference evidence CSV files."""
    ref_dir = base_dir / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)

    mf_isin = ref_dir / "MF_ISIN_MAPPING.csv"
    mf_isin.write_text(
        "INSTRUMENT_NAME,ISIN\n"
        "Parag Parikh Flexi Cap Fund - Direct Plan - Growth,INF879O01019\n"
        "Mirae Asset Large Cap Fund - Direct Plan - Growth,INF769K01018\n",
        encoding="utf-8",
    )

    benchmark_map = ref_dir / "BENCHMARK_MAPPING.csv"
    benchmark_map.write_text(
        "ISIN,Sector,Industry,Benchmark_ID,Yahoo_Ticker,Tax_Instrument_Type,Tax_Instrument_Subtype,Country,Geo,Geo_Subtype,Ticker\n"
        "INF879O01019,Financials,Asset Management,NIFTY50,^NSEI,EQUITY,EQUITY_MF,India,DOMESTIC,IN,PPFC\n"
        "INF769K01018,Financials,Asset Management,NIFTY50,^NSEI,EQUITY,EQUITY_MF,India,DOMESTIC,IN,MALC\n"
        "INE002A01018,Energy,Oil & Gas,NIFTY50,RELIANCE.NS,EQUITY,EQUITY_LISTED,India,DOMESTIC,IN,RELIANCE\n"
        "INE009A01021,Technology,IT Services,NIFTY50,INFY.NS,EQUITY,EQUITY_LISTED,India,DOMESTIC,IN,INFY\n"
        "US0378331005,Technology,Consumer Electronics,NIFTY50,AAPL,EQUITY,FOREIGN_EQUITY,United States,FOREIGN,US,AAPL\n",
        encoding="utf-8",
    )

    benchmark_master = ref_dir / "BENCHMARK_MASTER.csv"
    benchmark_master.write_text(
        "ID,Benchmark_Name,yF_Ticker,Currency\n"
        "NIFTY50,Nifty 50,^NSEI,INR\n"
        "SENSEX,BSE Sensex,^BSESN,INR\n",
        encoding="utf-8",
    )

    macro = ref_dir / "MACRO_PARAMETERS.csv"
    macro.write_text(
        "FY,FY_Start_Date,FY_End_Date,Debt_MF_Cutoff_Date,Inflation_Rate,Risk_Free_Rate,"
        "Estimated_Ordinary_Income_Tax_Rate,Equity_LTCG_Exemption,Equity_Listed_LTCG,"
        "Equity_Listed_STCG,Equity_Unlisted_LTCG,Equity_Unlisted_STCG,Gold_LTCG,Gold_STCG,"
        "Debt_MF_Pre_Cutoff_LTCG,Debt_MF_Pre_Cutoff_STCG,Debt_MF_Post_Cutoff_LTCG,"
        "Debt_MF_Post_Cutoff_STCG,Other_Debt_LTCG,Other_Debt_STCG,Default_LTCG,Default_STCG,Remarks\n"
        "2023-24,2023-04-01,2024-03-31,2023-03-31,0.06,0.07,0.30,100000,0.10,0.15,0.20,0.30,"
        "0.20,0.30,0.20,0.30,0.30,0.30,0.20,0.30,0.20,0.30,Finance Act 2023\n"
        "2024-25,2024-04-01,2025-03-31,2023-03-31,0.06,0.07,0.30,125000,0.125,0.20,0.20,0.30,"
        "0.20,0.30,0.20,0.30,0.30,0.30,0.20,0.30,0.20,0.30,Finance Act 2024\n",
        encoding="utf-8",
    )

    currency_map = ref_dir / "CURRENCY_MAPPING.csv"
    currency_map.write_text(
        "UID,Currency_Code,Target_Currency_Code,yF_Ticker,Currency_Name,Is_Active\n"
        "USD_INR,USD,INR,USDINR=X,US Dollar to Indian Rupee,true\n"
        "EUR_INR,EUR,INR,EURINR=X,Euro to Indian Rupee,true\n",
        encoding="utf-8",
    )

    opening_bal = ref_dir / "OPENING_BALANCE.csv"
    header = (
        "Z_PK,Z_ENT,Z_OPT,ZASSET_GROUP,ZASSET_ID,ZCATEGORY_ID,ZOPPOSITEAID,ZAID,"
        "ZCATEGORYID,ZCURRENCYID,ZFEE_ID,ZISDEL,ZISSYNCED,ZMARK,ZSYNCCHECK,ZSYNCVERSION,"
        "ZUTIME,ZDATE,ZAMOUNT,ZAMOUNTACCOUNT,ZAMOUNTSUB,ZSYNCTIME,ZASSET_NAME,ZASSET_NIC,"
        "ZCARDDIVIDID,ZCATEGORY_NAME,ZCONTENT,ZDO_TYPE,ZMONEY,ZASSETUID,ZCARDDIVIDEMONTH,"
        "ZCARDDIVIDEMONTHSTR,ZCARDDIVIDEUID,ZCARDTIMESTAMPSTR,ZCATEGORYUID,ZCURRENCY,"
        "ZCURRENCYUID,ZGSTD,ZLAT,ZLNG,ZMEMO,ZPAID,ZSMSORIGINE,ZSMSPARSECONTENTS,ZSMSRDATE,"
        "ZTOASSETUID,ZTXDATESTR,ZTXUIDFEE,ZTXUIDTRANS,ZUID,ZWTIME,ZZDATA1,ZZDATA2\n"
    )
    row_1 = (
        "1,1,1,1,1,1,0,1,1,1,0,0,1,0,0,1,1672531200,1672531200,100000.0,100000.0,0.0,"
        "1672531200.0,Savings Account,HDFC Savings,0,Opening Balance,Initial Corpus,0,100000.0,"
        "ASSET_HDFC,0,0,0,0,0,INR,CURR_INR,0,0.0,0.0,Initial deposit,1,0,0,0,0,"
        "2023-01-01 00:00:00,0,0,OP_001,00:00:00,0,0\n"
    )
    row_2 = (
        "2,1,1,1,2,1,0,2,1,1,0,0,1,0,0,1,1672531200,1672531200,25000.0,25000.0,0.0,"
        "1672531200.0,Wallet Cash,Physical Cash,0,Opening Balance,Cash in Hand,0,25000.0,"
        "ASSET_CASH,0,0,0,0,0,INR,CURR_INR,0,0.0,0.0,Cash reserve,1,0,0,0,0,"
        "2023-01-01 00:00:00,0,0,OP_002,00:00:00,0,0\n"
    )
    opening_bal.write_text(header + row_1 + row_2, encoding="utf-8")

    return {
        "mf_isin": mf_isin,
        "benchmark_mapping": benchmark_map,
        "benchmark_master": benchmark_master,
        "macro_parameters": macro,
        "currency_mapping": currency_map,
        "opening_balance": opening_bal,
    }


def generate_all_fixtures(output_dir: Path | None = None) -> None:
    """Generate all static evidence fixtures under target directory."""
    if output_dir is None:
        output_dir = Path(__file__).parent / "evidence"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    build_household_evidence(output_dir)
    build_mf_evidence(output_dir)
    build_stock_evidence(output_dir)
    build_us_stock_evidence(output_dir)
    build_reference_evidence(output_dir)
    print(f"Generated all static evidence fixtures in {output_dir}")


if __name__ == "__main__":
    generate_all_fixtures()
