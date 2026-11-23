"""System status, warehouse inventory, and Doctor health diagnostic tab.

Owns
----
- SystemTab: Comprehensive operational monitoring and diagnostic panel.
- Live pipeline lock state, database sizes, latest run/sync telemetry cards.
- Runtime environment, configuration paths, and warehouse table inventory metrics.
- Interactive Doctor diagnostic health check execution with actionable remediations.

Does not own
-------------
- Concrete database queries or DDL (owned by infrastructure.operator / warehouse).
- Direct network probing or lock file inspection (owned by infrastructure.operator).
"""

from __future__ import annotations

import os
import subprocess
import sys

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.operator import (
    DoctorReport,
    SystemInfo,
    SystemStatus,
)
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import Color

__all__ = ["SystemTab"]


def _format_size(num_bytes: int | None) -> str:
    """Format byte size into human-readable unit string."""
    if num_bytes is None:
        return "N/A"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def _open_folder_safely(folder_path: str | None) -> None:
    """Open folder in native platform file manager."""
    # pylint: disable=consider-using-with
    if not folder_path or not os.path.exists(folder_path):
        return
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder_path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
    except Exception:
        pass


# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: Subclassing untyped third-party ctk.CTkFrame base class
class SystemTab(ctk.CTkFrame):  # type: ignore[misc]
    """System health monitoring, environment metrics, and diagnostic doctor runner."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkFrame,
        engine: PersonalFinanceEngine | None = None,
        app_state: AppState | None = None,
    ) -> None:
        super().__init__(parent, fg_color=Color.BG)

        self.engine = engine or PersonalFinanceEngine()
        self.app_state = app_state

        self._cached_status: SystemStatus | None = None
        self._cached_info: SystemInfo | None = None
        self._cached_report: DoctorReport | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Top toolbar
        self.grid_rowconfigure(1, weight=1)  # Scrollable content cards

        self._build_top_toolbar()
        self._build_content_cards()

        # Lazy loading state
        self._loaded: bool = False

    def ensure_loaded(self) -> None:
        """Lazily load operational status and warehouse inventory on first view."""
        if not self._loaded:
            self._loaded = True
            self.refresh_status()

    # ── 1. Top Toolbar ────────────────────────────────────────────────────────

    def _build_top_toolbar(self) -> None:
        """Construct the top toolbar containing action triggers."""
        toolbar = ctk.CTkFrame(
            self,
            fg_color="#101624",
            height=44,
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 8))

        ctk.CTkLabel(
            toolbar,
            text="System Operations & Diagnostics",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#F8FAFC",
        ).pack(side="left", padx=14, pady=8)

        ctk.CTkButton(
            toolbar,
            text="🔄 Refresh Status",
            width=120,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self.refresh_status,
        ).pack(side="left", padx=6, pady=8)

        self.doctor_btn = ctk.CTkButton(
            toolbar,
            text="🩺 Run Doctor",
            width=115,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=Color.ACCENT,
            hover_color=Color.ACC_HOV,
            command=self.run_doctor,
        )
        self.doctor_btn.pack(side="left", padx=6, pady=8)

        ctk.CTkButton(
            toolbar,
            text="📂 Open Database Folder",
            width=165,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._open_db_folder,
        ).pack(side="right", padx=(6, 14), pady=8)

        ctk.CTkButton(
            toolbar,
            text="📂 Open Logs Folder",
            width=135,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._open_logs_folder,
        ).pack(side="right", padx=6, pady=8)

    # ── 2. Content Cards ──────────────────────────────────────────────────────

    def _build_content_cards(self) -> None:
        """Construct the scrollable body containing status, info, and doctor sections."""
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=Color.BG,
            corner_radius=0,
        )
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.scroll.grid_columnconfigure(0, weight=1)

        # 1. Operational Health Card
        self._build_operational_status_card()

        # 2. Environment & Warehouse Inventory Card
        self._build_inventory_card()

        # 3. Doctor Diagnostic Results Card
        self._build_doctor_results_card()

    # ── 3. Operational Status Card ────────────────────────────────────────────

    def _build_operational_status_card(self) -> None:
        """Card displaying real-time database presence, sizes, lock state, and latest run."""
        self.status_card = ctk.CTkFrame(
            self.scroll,
            fg_color="#0F1420",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        self.status_card.pack(fill="x", pady=(0, 12))
        self.status_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        header = ctk.CTkFrame(self.status_card, fg_color="#151D2E", height=32, corner_radius=0)
        header.grid(row=0, column=0, columnspan=4, sticky="ew")

        ctk.CTkLabel(
            header,
            text="OPERATIONAL SYSTEM STATUS",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94A3B8",
        ).pack(side="left", padx=12, pady=6)

        self.lock_badge = ctk.CTkLabel(
            header,
            text="● UNLOCKED",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#4ADE80",
            fg_color="#062817",
            corner_radius=4,
        )
        self.lock_badge.pack(side="right", padx=12, pady=6, ipady=1, ipadx=8)

        # Metric Tiles Container
        tiles_frame = ctk.CTkFrame(self.status_card, fg_color="transparent")
        tiles_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=12, pady=12)
        tiles_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Tile 1: DuckDB
        self.duckdb_val = self._create_metric_tile(
            tiles_frame, 0, "DuckDB Warehouse", "Checking..."
        )
        # Tile 2: SQLite
        self.sqlite_val = self._create_metric_tile(
            tiles_frame, 1, "Raw Store SQLite", "Checking..."
        )
        # Tile 3: Latest Run
        self.latest_run_val = self._create_metric_tile(
            tiles_frame, 2, "Latest Run Status", "Checking..."
        )
        # Tile 4: Stale / Recovery
        self.recovery_val = self._create_metric_tile(
            tiles_frame, 3, "Recovery Required", "Checking..."
        )

        # Sub-detail row
        self.status_detail_lbl = ctk.CTkLabel(
            self.status_card,
            text="",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#64748B",
            anchor="w",
        )
        self.status_detail_lbl.grid(
            row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 10)
        )

    def _create_metric_tile(
        self, parent: ctk.CTkFrame, col: int, title: str, default_val: str
    ) -> ctk.CTkLabel:
        """Create a metrics tile inside an operational status card."""
        tile = ctk.CTkFrame(
            parent, fg_color="#0A0E17", corner_radius=6, border_width=1, border_color="#1E293B"
        )
        tile.grid(row=0, column=col, sticky="ew", padx=4, pady=4)

        ctk.CTkLabel(
            tile,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748B",
        ).pack(anchor="w", padx=10, pady=(8, 2))

        val_lbl = ctk.CTkLabel(
            tile,
            text=default_val,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#F8FAFC",
        )
        val_lbl.pack(anchor="w", padx=10, pady=(0, 8))

        return val_lbl

    # ── 4. Environment & Inventory Card ───────────────────────────────────────

    def _build_inventory_card(self) -> None:
        """Card displaying runtime metadata and warehouse contract counts."""
        self.info_card = ctk.CTkFrame(
            self.scroll,
            fg_color="#0F1420",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        self.info_card.pack(fill="x", pady=(0, 12))
        self.info_card.grid_columnconfigure((0, 1, 2), weight=1)

        header = ctk.CTkFrame(self.info_card, fg_color="#151D2E", height=32, corner_radius=0)
        header.grid(row=0, column=0, columnspan=3, sticky="ew")

        ctk.CTkLabel(
            header,
            text="RUNTIME ENVIRONMENT & CONTRACT INVENTORY",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94A3B8",
        ).pack(side="left", padx=12, pady=6)

        # 3 Metric Cards for Tables
        pills_frame = ctk.CTkFrame(self.info_card, fg_color="transparent")
        pills_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 6))
        pills_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.bronze_cnt_lbl = self._create_metric_tile(pills_frame, 0, "Bronze Contracts", "-")
        self.silver_cnt_lbl = self._create_metric_tile(pills_frame, 1, "Silver Contracts", "-")
        self.gold_cnt_lbl = self._create_metric_tile(pills_frame, 2, "Gold Contracts", "-")

        # Metadata text rows
        self.meta_frame = ctk.CTkFrame(self.info_card, fg_color="transparent")
        self.meta_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=14, pady=(6, 12))
        self.meta_frame.grid_columnconfigure(1, weight=1)

    # ── 5. Doctor Health Check Results Card ───────────────────────────────────

    def _build_doctor_results_card(self) -> None:
        """Card displaying the latest Doctor diagnostic report results."""
        self.doctor_card = ctk.CTkFrame(
            self.scroll,
            fg_color="#0F1420",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        self.doctor_card.pack(fill="x", pady=(0, 12))
        self.doctor_card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.doctor_card, fg_color="#151D2E", height=32, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            header,
            text="SYSTEM DOCTOR DIAGNOSTIC HEALTH REPORT",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94A3B8",
        ).pack(side="left", padx=12, pady=6)

        self.doctor_status_badge = ctk.CTkLabel(
            header,
            text="NOT RUN",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
            fg_color="#1E293B",
            corner_radius=4,
        )
        self.doctor_status_badge.pack(side="right", padx=12, pady=6, ipady=1, ipadx=8)

        # Dynamic check rows container
        self.checks_container = ctk.CTkFrame(self.doctor_card, fg_color="transparent")
        self.checks_container.grid(row=1, column=0, sticky="ew", padx=12, pady=12)
        self.checks_container.grid_columnconfigure(0, weight=1)

        self.doctor_placeholder = ctk.CTkLabel(
            self.checks_container,
            text="Click '🩺 Run Doctor' to perform deep integrity diagnostics across configuration, storage, and runtime providers.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748B",
        )
        self.doctor_placeholder.pack(pady=20)

    # ── 6. Operational State Updates ──────────────────────────────────────────

    def refresh_status(self) -> None:
        """Fetch and render updated system status and inventory."""
        cfg_path = self.app_state.active_config_path if self.app_state else None
        status = self.engine.get_system_status(cfg_path)
        info = self.engine.get_system_info(cfg_path)

        self._cached_status = status
        self._cached_info = info

        # 1. Update Status Tiles
        if status.is_locked:
            self.lock_badge.configure(
                text="🔒 LOCKED",
                text_color="#EF4444",
                fg_color="#450A0A",
            )
        else:
            self.lock_badge.configure(
                text="● UNLOCKED",
                text_color="#4ADE80",
                fg_color="#062817",
            )

        duck_status = (
            f"✓ Present ({_format_size(status.duckdb_size_bytes)})"
            if status.duckdb_exists
            else "✗ Missing"
        )
        self.duckdb_val.configure(
            text=duck_status,
            text_color="#4ADE80" if status.duckdb_exists else "#EF4444",
        )

        sqlite_status = (
            f"✓ Present ({_format_size(status.sqlite_size_bytes)})"
            if status.sqlite_exists
            else "✗ Missing"
        )
        self.sqlite_val.configure(
            text=sqlite_status,
            text_color="#4ADE80" if status.sqlite_exists else "#EF4444",
        )

        run_st = status.latest_run_status or "None"
        run_col = (
            "#4ADE80" if run_st == "SUCCESS" else ("#EF4444" if run_st == "FAILED" else "#94A3B8")
        )
        self.latest_run_val.configure(text=run_st, text_color=run_col)

        rec_cnt = status.recovery_required_count
        rec_col = "#4ADE80" if rec_cnt == 0 else "#EF4444"
        self.recovery_val.configure(text=f"{rec_cnt} Required", text_color=rec_col)

        # Sub-detail
        details: list[str] = []
        if status.latest_run_id:
            details.append(f"Run ID: {status.latest_run_id}")
        if status.latest_run_started_at:
            details.append(f"Started: {status.latest_run_started_at}")
        if status.latest_run_finished_at:
            details.append(f"Finished: {status.latest_run_finished_at}")
        if status.stale_runs_count:
            details.append(f"Stale Runs: {status.stale_runs_count}")
        self.status_detail_lbl.configure(text="  |  ".join(details))

        # 2. Update Contract Counts
        self.bronze_cnt_lbl.configure(text=f"{info.bronze_tables_count} Tables")
        self.silver_cnt_lbl.configure(text=f"{info.silver_tables_count} Tables")
        self.gold_cnt_lbl.configure(text=f"{info.gold_tables_count} Tables")

        # 3. Update Environment Meta Rows
        for widget in self.meta_frame.winfo_children():
            widget.destroy()

        meta_rows = [
            ("PFETL Version:", f"{info.version} (Python {info.python_version} on {info.platform})"),
            ("Executable:", info.executable),
            ("Active Config TOML:", info.config_path or "None"),
            ("Active Rules TOML:", info.rules_path or "None"),
            ("DuckDB Warehouse:", info.database_path or "None"),
            ("Raw Store SQLite:", info.raw_store_path or "None"),
            ("Household Source:", info.household_db_path or "None"),
            ("Statements Root:", info.statements_root or "None"),
            (
                "Warehouse Schemas:",
                ", ".join(info.warehouse_schemas) if info.warehouse_schemas else "None",
            ),
        ]

        for r_idx, (k, v) in enumerate(meta_rows):
            ctk.CTkLabel(
                self.meta_frame,
                text=k,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color="#64748B",
                anchor="w",
            ).grid(row=r_idx, column=0, sticky="w", padx=(4, 12), pady=2)

            ctk.CTkLabel(
                self.meta_frame,
                text=v,
                font=ctk.CTkFont(family="Consolas", size=10),
                text_color="#CBD5E1",
                anchor="w",
            ).grid(row=r_idx, column=1, sticky="w", padx=4, pady=2)

    # ── 7. Run Doctor Execution ───────────────────────────────────────────────

    def run_doctor(self) -> None:
        """Execute full doctor health checks and display diagnostic cards."""
        cfg_path = self.app_state.active_config_path if self.app_state else None
        rules_path = self.app_state.active_rules_path if self.app_state else None

        self.doctor_btn.configure(state="disabled", text="Running...")
        self.update_idletasks()

        try:
            report = self.engine.run_doctor(cfg_path, rules_path)
            self._cached_report = report
            self._render_doctor_report(report)
        finally:
            self.doctor_btn.configure(state="normal", text="🩺 Run Doctor")

    def _render_doctor_report(self, report: DoctorReport) -> None:
        """Render all DoctorCheckResult cards with status and remediation hints."""
        for widget in self.checks_container.winfo_children():
            widget.destroy()

        # Update Overall Badge
        badge_styles = {
            "PASS": ("● PASS", "#4ADE80", "#062817"),
            "WARN": ("▲ WARNING", "#FBBF24", "#2D1E04"),
            "FAIL": ("✖ FAIL", "#F87171", "#2E0B0B"),
        }
        text_badge, text_col, bg_col = badge_styles.get(
            report.overall_status, ("UNKNOWN", "#94A3B8", "#1E293B")
        )
        self.doctor_status_badge.configure(
            text=f"{text_badge} ({report.passed_count} Passed, {report.warn_count} Warn, {report.failed_count} Fail)",
            text_color=text_col,
            fg_color=bg_col,
        )

        if not report.checks:
            ctk.CTkLabel(
                self.checks_container,
                text="No diagnostic checks returned by operator service.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#64748B",
            ).pack(pady=10)
            return

        for check in report.checks:
            chk_frame = ctk.CTkFrame(
                self.checks_container,
                fg_color="#0A0E17",
                corner_radius=6,
                border_width=1,
                border_color="#1E293B",
            )
            chk_frame.pack(fill="x", pady=4)
            chk_frame.grid_columnconfigure(1, weight=1)

            st_text, st_tcol, st_bgcol = badge_styles.get(
                check.status, (check.status, "#94A3B8", "#1E293B")
            )

            # Check Status Badge
            ctk.CTkLabel(
                chk_frame,
                text=st_text,
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                text_color=st_tcol,
                fg_color=st_bgcol,
                corner_radius=4,
                width=75,
            ).grid(row=0, column=0, padx=8, pady=8, ipady=2)

            # Name & Message
            info_frame = ctk.CTkFrame(chk_frame, fg_color="transparent")
            info_frame.grid(row=0, column=1, sticky="ew", padx=4, pady=8)

            ctk.CTkLabel(
                info_frame,
                text=check.name,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#F8FAFC",
                anchor="w",
            ).pack(anchor="w")

            ctk.CTkLabel(
                info_frame,
                text=check.message,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="#94A3B8",
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))

            # Remediation Hint (for WARN and FAIL)
            if check.remediation:
                rem_box = ctk.CTkFrame(
                    chk_frame,
                    fg_color="#1A1811" if check.status == "WARN" else "#1F0E0E",
                    corner_radius=4,
                    border_width=1,
                    border_color="#422006" if check.status == "WARN" else "#450A0A",
                )
                rem_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))

                ctk.CTkLabel(
                    rem_box,
                    text=f"💡 Remediation: {check.remediation}",
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color="#FDE047" if check.status == "WARN" else "#FCA5A5",
                    anchor="w",
                ).pack(anchor="w", padx=8, pady=6)

    # ── 8. Folder Launchers ───────────────────────────────────────────────────

    def _open_db_folder(self) -> None:
        """Open database directory in native file explorer."""
        if self._cached_info and self._cached_info.database_path:
            db_dir = os.path.dirname(self._cached_info.database_path)
            _open_folder_safely(db_dir)
        elif self.app_state and self.app_state.active_config_path:
            base_dir = os.path.dirname(self.app_state.active_config_path)
            _open_folder_safely(base_dir)

    def _open_logs_folder(self) -> None:
        """Open logs directory in native file explorer."""
        cfg_path = self.app_state.active_config_path if self.app_state else None
        log_dir = self.engine.get_logs_directory(cfg_path)
        _open_folder_safely(str(log_dir))
