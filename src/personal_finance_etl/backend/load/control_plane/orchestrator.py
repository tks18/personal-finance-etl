from personal_finance_etl.backend.load.control_plane.artifact_repo import ArtifactRepository
from personal_finance_etl.backend.load.control_plane.connection import SQLiteManager
from personal_finance_etl.backend.load.control_plane.file_sync import FileSyncService
from personal_finance_etl.backend.load.control_plane.run_repo import RunRepository


class ControlPlane:
    """
    The single, authoritative orchestrator for all ETL Control Plane operations.
    Encapsulates database connections, artifact state tracking, pipeline run lifecycle,
    and file synchronization.
    """

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db = SQLiteManager(base_path, db_name)
        self.artifacts = ArtifactRepository(self.db)
        self.runs = RunRepository(self.db)
        self.file_sync = FileSyncService(self.artifacts)

    # ---------------------------------------------------------
    # Connection Lifecycle Wrappers
    # ---------------------------------------------------------
    def open(self) -> None:
        self.db.open()

    def close(self) -> None:
        self.db.close()

    def ensure_schema(self) -> None:
        self.db.ensure_schema()

    def begin_transaction(self) -> None:
        self.db.begin_transaction()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
