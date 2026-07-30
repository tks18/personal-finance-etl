DIMENSIONS_DDL = """
-- DDL: d_Calendar
CREATE TABLE d_Calendar (
    Date DATE PRIMARY KEY,
    Day INTEGER,
    "Day Name" TEXT,
    "Day Name Short" TEXT,
    "Day Ordinal" INTEGER,
    "Day Ordinal Name" TEXT,
    Weekday INTEGER,
    Week INTEGER,
    "Week Ordinal" INTEGER,
    "Week Ordinal Name" TEXT,
    Month INTEGER,
    "Month Name" TEXT,
    "Month Name Short" TEXT,
    Quarter INTEGER,
    "Quarter Name" TEXT,
    Year INTEGER,
    "FY Month" INTEGER,
    "FY Year" INTEGER,
    "Start of Month" DATE,
    "FY Start of Month" DATE,
    "FY Quarter" INTEGER,
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
    IS_WEEKEND INTEGER
);

-- DDL: d_Income_Category
CREATE TABLE d_Income_Category (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO INTEGER,
    MODIFY_DATE INTEGER,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE INTEGER,
    CATEGORY_NAME_SHORT TEXT
);

-- DDL: d_Income_Subcategory
CREATE TABLE d_Income_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO INTEGER,
    MODIFY_DATE INTEGER,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE INTEGER,
    CATEGORY_ID TEXT,
    CATEGORY_GROUPS TEXT,
    FOREIGN KEY (CATEGORY_ID) REFERENCES d_Income_Category(UID)
);

-- DDL: d_Expense_Category
CREATE TABLE d_Expense_Category (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO INTEGER,
    MODIFY_DATE INTEGER,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE INTEGER
);

-- DDL: d_Expense_Subcategory
CREATE TABLE d_Expense_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO INTEGER,
    MODIFY_DATE INTEGER,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE INTEGER,
    CATEGORY_ID TEXT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Expense_Category(UID)
);

-- DDL: d_Asset_Category
CREATE TABLE d_Asset_Category (
    __file_name__ TEXT, __folder_path__ TEXT, DEVICE_ID INTEGER,
    UID TEXT PRIMARY KEY,
    USE_TIME INTEGER,
    ASSET_GROUP TEXT,
    TYPE INTEGER,
    ORDER_SEQUENCE INTEGER
);

-- DDL: d_Asset_Subcategory
CREATE TABLE d_Asset_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO INTEGER,
    CARD_STATEMENT_DATE INTEGER,
    CARD_PAYMENT_DATE INTEGER,
    ASSET_NAME TEXT,
    ORDER_SEQUENCE INTEGER,
    ASSET_DESCRIPTION TEXT,
    NOTES INTEGER,
    TRANSFER_EXPENSE INTEGER,
    CARD_AUTOPAY INTEGER,
    ADDED_TIME INTEGER,
    UID TEXT PRIMARY KEY,
    CURRENCY_ID TEXT,
    AUTOPAY_ASSET_ID INTEGER,
    ASSET_GROUP_ID TEXT,
    FOREIGN KEY(ASSET_GROUP_ID) REFERENCES d_Asset_Category(UID)
);

-- DDL: d_Currency
CREATE TABLE d_Currency (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO INTEGER,
    UID TEXT PRIMARY KEY,
    CURRENCY_NAME TEXT,
    ISO TEXT,
    MAIN_ISO TEXT,
    ORDER_SEQUENCE INTEGER,
    RATE REAL,
    SYMBOL TEXT,
    INSERT_TYPE TEXT,
    SYMBOL_POSITION TEXT,
    IS_MAIN_CURRENCY INTEGER,
    IS_SHOW INTEGER,
    MODIFY_DATE INTEGER,
    DECIMAL_POINT INTEGER
);
"""
