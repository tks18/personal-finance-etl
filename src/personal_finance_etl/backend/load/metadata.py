import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.utils.logger import logger


class MetaLayer:
    """Manages recording run metadata, table row counts, and rules snapshots to the meta schema."""

    def __init__(
        self, db_manager: DuckDBManager, run_id: str, cfg: Settings, rules: FinancialRules | None
    ):
        self.db_manager = db_manager
        self.run_id = run_id
        self.cfg = cfg
        self.rules = rules

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Records table sizes and financial rules into the meta schema."""
        logger.info("Recording table metrics and financial rules to Meta Layer...")

        # 1. Record Table Row Counts
        for table_name, df in dfs.items():
            try:
                count = df.height
            except Exception:
                count = 0

            schema = "gold" if "p_tf_" in table_name else "silver"
            self.db_manager.conn.execute(
                """
                INSERT INTO meta.m_Table_Row_Counts 
                (run_id, schema_name, table_name, row_count, generated_at) 
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [self.run_id, schema, table_name, count],
            )

        # 2. Record Financial Rules Snapshot
        if self.rules is not None:
            rule_records = self.rules.export_to_db_records()
            for record in rule_records:
                self.db_manager.conn.execute(
                    """
                    INSERT INTO meta.m_Financial_Rules 
                    (run_id, Rule_Domain, Rule_Type, Target_Level, Target_ID) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        self.run_id,
                        record["Rule_Domain"],
                        record["Rule_Type"],
                        record["Target_Level"],
                        record["Target_ID"],
                    ],
                )

        # 3. Record Application Settings Snapshot
        setting_records = self.cfg.export_to_db_records()
        for record in setting_records:
            self.db_manager.conn.execute(
                """
                INSERT INTO meta.m_Settings 
                (run_id, Setting_Group, Setting_Key, Setting_Value) 
                VALUES (?, ?, ?, ?)
                """,
                [
                    self.run_id,
                    record["Setting_Group"],
                    record["Setting_Key"],
                    record["Setting_Value"],
                ],
            )

        logger.info("Meta layer load complete.")
