from src.load.schema.dimensions import DIMENSIONS_DDL
from src.load.schema.facts import FACTS_DDL
from src.load.schema.investments import INVESTMENTS_DDL
from src.load.schema.pragmas import SQLITE_PRAGMAS

SQLITE_SCHEMA_DDL = "\n".join([DIMENSIONS_DDL, FACTS_DDL, INVESTMENTS_DDL])

__all__ = ["SQLITE_PRAGMAS", "SQLITE_SCHEMA_DDL"]
