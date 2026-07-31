DIMENSIONS_DDL = """
-- DDL: d_Calendar
CREATE TABLE d_Calendar (
    Date DATE PRIMARY KEY,
    Day BIGINT,
    "Day Name" TEXT,
    "Day Name Short" TEXT,
    "Day Ordinal" BIGINT,
    "Day Ordinal Name" TEXT,
    Weekday BIGINT,
    Week BIGINT,
    "Week Ordinal" BIGINT,
    "Week Ordinal Name" TEXT,
    Month BIGINT,
    "Month Name" TEXT,
    "Month Name Short" TEXT,
    Quarter BIGINT,
    "Quarter Name" TEXT,
    Year BIGINT,
    "FY Month" BIGINT,
    "FY Year" BIGINT,
    "Start of Month" DATE,
    "FY Start of Month" DATE,
    "FY Quarter" BIGINT,
    "FY Quarter Name" TEXT,
    "Month - Year" TEXT,
    "Short Month - Year" TEXT,
    "Quarter - Year" TEXT,
    "FY Quarter - Year" TEXT,
    "Financial Year" TEXT,
    "Start of Quarter" DATE,
    "FY Start of Quarter" DATE,
    "End of Month" DATE,
    "FY End of Month" DATE,
    "End of Quarter" DATE,
    "FY End of Quarter" DATE,
    "V Short Month - Year" TEXT,
    "Week - Year" TEXT,
    "Week Name" TEXT,
    "Start of Week" DATE,
    "End of Week" DATE,
    "Week Name - Year" TEXT,
    IS_WEEKEND BIGINT
);

-- DDL: d_Income_Category
CREATE TABLE d_Income_Category (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    CATEGORY_NAME_SHORT TEXT
);

-- DDL: d_Income_Subcategory
CREATE TABLE d_Income_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    CATEGORY_ID TEXT,
    CATEGORY_GROUPS TEXT,
    FOREIGN KEY (CATEGORY_ID) REFERENCES d_Income_Category(UID)
);

-- DDL: d_Expense_Category
CREATE TABLE d_Expense_Category (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT
);

-- DDL: d_Expense_Subcategory
CREATE TABLE d_Expense_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    CATEGORY_ID TEXT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Expense_Category(UID)
);

-- DDL: d_Asset_Category
CREATE TABLE d_Asset_Category (
    __file_name__ TEXT, __folder_path__ TEXT, DEVICE_ID BIGINT,
    UID TEXT PRIMARY KEY,
    USE_TIME BIGINT,
    ASSET_GROUP TEXT,
    TYPE BIGINT,
    ORDER_SEQUENCE BIGINT
);

-- DDL: d_Asset_Subcategory
CREATE TABLE d_Asset_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    CARD_STATEMENT_DATE BIGINT,
    CARD_PAYMENT_DATE BIGINT,
    ASSET_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    ASSET_DESCRIPTION TEXT,
    NOTES TEXT,
    TRANSFER_EXPENSE BIGINT,
    CARD_AUTOPAY BIGINT,
    ADDED_TIME BIGINT,
    UID TEXT PRIMARY KEY,
    CURRENCY_ID TEXT,
    AUTOPAY_ASSET_ID TEXT,
    ASSET_GROUP_ID TEXT,
    FOREIGN KEY(ASSET_GROUP_ID) REFERENCES d_Asset_Category(UID)
);

-- DDL: d_Currency
CREATE TABLE d_Currency (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    UID TEXT PRIMARY KEY,
    CURRENCY_NAME TEXT,
    ISO TEXT,
    MAIN_ISO TEXT,
    ORDER_SEQUENCE BIGINT,
    RATE DOUBLE,
    SYMBOL TEXT,
    INSERT_TYPE TEXT,
    SYMBOL_POSITION TEXT,
    IS_MAIN_CURRENCY BIGINT,
    IS_SHOW BIGINT,
    MODIFY_DATE BIGINT,
    DECIMAL_POINT BIGINT
);
"""
