import concurrent.futures
from datetime import date, timedelta

import polars as pl

from src.engines.benchmark.cache import BenchmarkCacheManager
from src.engines.benchmark.fetcher import BenchmarkDataFetcher
from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus, LogLevel


class BenchmarkEngine:
    """
    Downloads benchmark price data concurrently for all tickers defined in a master CSV.
    Pushes progress tuples of (message, data_or_None, progress_float) to status_queue.
    """

    def __init__(
        self,
        df_m: pl.DataFrame,
        status_queue: ILogger,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        max_workers: int = 8,
        target_db_base_path: str | None = None,
        current_db_path: str | None = None,
    ) -> None:
        self.df_m = df_m
        self.status_queue = status_queue
        self.start_date = start_date
        self.end_date = end_date
        self.max_workers = max_workers
        self.cache_manager = BenchmarkCacheManager(
            target_db_base_path, current_db_path, status_queue
        )

    def _resolve_dates(
        self, df_market: pl.DataFrame | None, df_purchase: pl.DataFrame | None
    ) -> tuple[date, date]:
        min_market, max_market, min_purch = None, None, None

        if df_market is not None and not df_market.is_empty():
            market_dates = df_market.select(pl.col("Date").drop_nulls())
            if not market_dates.is_empty():
                min_market = market_dates.select(pl.min("Date")).item()
                max_market = market_dates.select(pl.max("Date")).item()

        if df_purchase is not None and not df_purchase.is_empty():
            purch_dates = df_purchase.select(pl.col("Date").drop_nulls())
            if not purch_dates.is_empty():
                min_purch = purch_dates.select(pl.min("Date")).item()

        valid_starts = [d for d in [min_market, min_purch] if d is not None]
        start = min(valid_starts) if valid_starts else date(2000, 1, 1)
        end = max_market if max_market else date.today()

        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)

        return start, end

    def run(
        self, df_market: pl.DataFrame | None = None, df_purchase: pl.DataFrame | None = None
    ) -> pl.DataFrame:
        try:
            if self.start_date is None or self.end_date is None:
                self.start_date, self.end_date = self._resolve_dates(df_market, df_purchase)

            self.status_queue.put(
                EngineStatus(
                    msg="Loading Benchmark Master...", data=None, progress=0.05, level=LogLevel.STEP
                )
            )
            df_m = self.df_m

            required_cols = ["ID", "Benchmark_Name", "yF_Ticker", "Currency"]
            missing_cols = [c for c in required_cols if c not in df_m.columns]
            if missing_cols:
                self.status_queue.put(
                    EngineStatus(
                        msg=f"Error: Missing columns in Benchmark Master: {missing_cols}",
                        data=None,
                        progress=0.0,
                        level=LogLevel.ERROR,
                    )
                )
                return pl.DataFrame()

            tickers_df = df_m.to_dicts()
            total = len(tickers_df)

            if not self.start_date or not self.end_date:
                self.status_queue.put(
                    EngineStatus(
                        msg="Error: Start Date and End Date are required for the Downloader.",
                        data=None,
                        progress=0.0,
                        level=LogLevel.ERROR,
                    )
                )
                return pl.DataFrame()

            if isinstance(self.start_date, str):
                start_dt = date.fromisoformat(self.start_date)
            else:
                start_dt = self.start_date

            if isinstance(self.end_date, str):
                end_dt = date.fromisoformat(self.end_date)
            else:
                end_dt = self.end_date

            cached_df = self.cache_manager.get_cached_benchmark_data()
            if cached_df is not None:
                self.status_queue.put(
                    EngineStatus(
                        msg="Validating cached benchmark data...",
                        data=None,
                        progress=0.08,
                        level=LogLevel.STEP,
                    )
                )

            base_fetch_start = start_dt - timedelta(days=15)
            df_full_idx = pl.DataFrame(
                {"Date": pl.date_range(start_dt, end_dt, "1d", eager=True).cast(pl.Date)}
            )

            all_dfs = []

            logger.info(f"Starting concurrent download for {total} tickers...")
            self.status_queue.put(
                EngineStatus(
                    msg="",
                    data=None,
                    progress=0.1,
                    level=LogLevel.STEP,
                )
            )

            processed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(
                        BenchmarkDataFetcher.fetch_ticker,
                        row,
                        start_dt,
                        end_dt,
                        base_fetch_start,
                        df_full_idx,
                        cached_df,
                    ): row
                    for row in tickers_df
                }

                for future in concurrent.futures.as_completed(futures):
                    processed += 1
                    prog = 0.1 + 0.85 * (processed / total)

                    try:
                        df_pl, row, msg = future.result()
                        level = (
                            LogLevel.WARNING
                            if "Warning" in (msg or "") or "⚠" in (msg or "")
                            else LogLevel.INFO
                        )
                        if msg:
                            if level == LogLevel.WARNING:
                                logger.warning(msg)
                            else:
                                logger.debug(msg)

                        self.status_queue.put(
                            EngineStatus(msg="", data=None, progress=prog, level=level)
                        )

                        if df_pl is not None and not df_pl.is_empty():
                            all_dfs.append(df_pl)
                    except Exception as e:
                        ticker = futures[future].get("yF_Ticker", "Unknown")
                        self.status_queue.put(
                            EngineStatus(
                                msg=f"Error: Critical thread failure on {ticker}: {str(e)}",
                                data=None,
                                progress=prog,
                                level=LogLevel.ERROR,
                            )
                        )

            if not all_dfs:
                return pl.DataFrame()

            final_df = pl.concat(all_dfs, how="vertical")

            logger.info("Benchmark Downloader successfully processed all tickers.")
            self.status_queue.put(
                EngineStatus(
                    msg="",
                    data=None,
                    progress=1.0,
                    level=LogLevel.SUCCESS,
                )
            )
            return final_df

        except Exception as e:
            self.status_queue.put(
                EngineStatus(
                    msg=f"Critical Benchmark Downloader Error: {str(e)}",
                    data=None,
                    progress=1.0,
                    level=LogLevel.ERROR,
                )
            )
            return pl.DataFrame()
