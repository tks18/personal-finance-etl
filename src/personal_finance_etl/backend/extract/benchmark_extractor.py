import concurrent.futures
import io
import time
import uuid
from datetime import date, timedelta

import polars as pl
import yfinance as yf  # type: ignore[import-untyped]

from personal_finance_etl.backend.load.control_plane import ControlPlane
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class BenchmarkExtractor:
    """
    Fetches missing delta from yfinance, chunks by year, serializes to Parquet,
    and injects directly into the Raw Store.
    """

    def __init__(
        self,
        cp: ControlPlane,
        status_queue: ILogger,
        max_workers: int = 8,
    ) -> None:
        self.cp = cp
        self.status_queue = status_queue
        self.max_workers = max_workers

    def _fetch_ticker_delta(
        self, row: dict[str, str], start_dt: date, end_dt: date, max_cached_date: date | None
    ) -> tuple[pl.DataFrame, str | None]:
        ticker = str(row.get("yF_Ticker", "")).strip()
        if not ticker:
            logger.debug(f"[Benchmark Extractor] Skipping empty ticker {row.get('ID')}")
            return pl.DataFrame(), f"Warning: Skipping empty ticker {row.get('ID')}"

        fetch_start = start_dt - timedelta(days=15)
        if max_cached_date and max_cached_date >= fetch_start:
            fetch_start = max_cached_date + timedelta(days=1)

        if fetch_start > end_dt:
            logger.debug(
                f"[Benchmark Extractor] {ticker} fully cached up to {end_dt}. Skipping API fetch."
            )
            return pl.DataFrame(), f"✓ {ticker} fully cached up to {end_dt}"

        logger.debug(f"[Benchmark Extractor] API Fetching {ticker} from {fetch_start} to {end_dt}")
        hist_pd = None
        for attempt in range(3):
            try:
                ticker_obj = yf.Ticker(ticker)
                hist_pd = ticker_obj.history(  # pyright: ignore
                    start=fetch_start, end=end_dt + timedelta(days=1)
                )
                break
            except Exception as e:
                logger.warning(
                    f"[Benchmark Extractor] Attempt {attempt + 1}/3 failed for {ticker}: {e}"
                )
                if attempt == 2:
                    return pl.DataFrame(), f"Error on {ticker}: {str(e)}"
                time.sleep(1 + attempt * 2)

        if hist_pd is None or hist_pd.empty:
            logger.debug(f"[Benchmark Extractor] No data returned from API for {ticker}.")
            return pl.DataFrame(), f"⚠ No new data fetched for {ticker}"

        hist_pd.index = hist_pd.index.tz_localize(None).normalize()  # pyright: ignore
        hist_pl = pl.from_pandas(hist_pd.reset_index())

        if "Date" not in hist_pl.columns:
            hist_pl = hist_pl.rename({"index": "Date"})

        df_new = hist_pl.select(
            [pl.col("Date").cast(pl.Date), pl.col("Close").cast(pl.Float64)]
        ).filter(pl.col("Close").is_not_null())

        df_new = df_new.with_columns(
            pl.lit(row["ID"]).alias("ID"),
            pl.lit(row["Benchmark_Name"]).alias("Benchmark_Name"),
            pl.lit(ticker).alias("yF_Ticker"),
            pl.lit(row["Currency"]).alias("Currency"),
        )

        logger.debug(f"[Benchmark Extractor] Parsed {df_new.height} new records for {ticker}.")

        warn_msg = None
        pct_drops = hist_pd["Close"].pct_change()  # pyright: ignore
        huge_drops = pct_drops[pct_drops < -0.4]  # pyright: ignore
        if not huge_drops.empty:  # pyright: ignore
            drop_dts = [d.strftime("%Y-%m-%d") for d in huge_drops.index]  # pyright: ignore
            warn_msg = f"⚠ Anomalous drops (>40%) in {ticker} on {', '.join(drop_dts)}"
            logger.warning(f"[Benchmark Extractor] {warn_msg}")

        msg = f"✓ API Fetched {ticker} ({fetch_start} to {end_dt}) - {df_new.height} rows"
        if warn_msg:
            msg += f". {warn_msg}"

        return df_new, msg

    def extract_benchmark_delta(
        self,
        df_m: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
        df_bronze_cached: pl.DataFrame,
    ) -> tuple[pl.DataFrame, list[str]]:
        """
        Executes parallel fetching, chunks results by year, injects Parquet bytes to Raw Store,
        and returns a list of injected virtual file paths to be passed to BronzeLayer.load.
        """
        required_cols = ["ID", "Benchmark_Name", "yF_Ticker", "Currency"]
        missing_cols = [c for c in required_cols if c not in df_m.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in Benchmark Master: {missing_cols}")

        tickers_df = df_m.to_dicts()
        total = len(tickers_df)
        all_new_data: list[pl.DataFrame] = []

        # Determine max cached date per ticker
        cache_map: dict[str, date] = {}
        if not df_bronze_cached.is_empty():
            aggs = df_bronze_cached.group_by("yF_Ticker").agg(pl.max("Date").alias("MaxDate"))
            for r in aggs.to_dicts():
                cache_map[r["yF_Ticker"]] = r["MaxDate"]

        self.status_queue.put(
            EngineStatus(
                msg=f"Starting benchmark extractor for {total} tickers...",
                data=None,
                progress=0.1,
                level=LogLevel.STEP,
            )
        )

        processed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._fetch_ticker_delta,
                    row,
                    global_start_date,
                    global_end_date,
                    cache_map.get(str(row.get("yF_Ticker", "")).strip()),
                ): row
                for row in tickers_df
            }

            for future in concurrent.futures.as_completed(futures):
                processed += 1
                prog = 0.1 + 0.4 * (processed / total)
                try:
                    df_pl, msg = future.result()
                    level = LogLevel.INFO
                    if "Error" in (msg or ""):
                        level = LogLevel.ERROR
                    elif "Warning" in (msg or "") or "⚠" in (msg or ""):
                        level = LogLevel.WARNING

                    if msg:
                        self.status_queue.put(
                            EngineStatus(msg=msg, data=None, progress=prog, level=level)
                        )

                    if not df_pl.is_empty():
                        all_new_data.append(df_pl)
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

        if not all_new_data:
            return pl.DataFrame(), []

        df_combined = pl.concat(all_new_data, how="diagonal")
        df_combined = df_combined.with_columns(pl.col("Date").dt.year().alias("Year"))

        years = df_combined["Year"].unique().to_list()
        injected_files: list[str] = []
        df_final_chunks: list[pl.DataFrame] = []

        for year in years:
            df_year = df_combined.filter(pl.col("Year") == year).drop("Year")

            # Serialize to Parquet (without __file_name__)
            buf = io.BytesIO()
            df_year.write_parquet(buf)
            raw_bytes = buf.getvalue()

            run_uuid = str(uuid.uuid4())[:8]
            filename = f"benchmark_delta_{year}_{run_uuid}.parquet"
            virtual_path = self.cp.artifacts.inject_virtual_file(
                filename=filename, category="benchmark_history", raw_bytes=raw_bytes
            )
            injected_files.append(virtual_path)

            # Append to final chunks with file tracking metadata
            df_final_chunks.append(
                df_year.with_columns(
                    pl.lit(filename).alias("__file_name__"),
                    pl.lit(virtual_path).alias("__folder_path__"),
                )
            )

        logger.info(
            f"Benchmark Extractor injected {len(injected_files)} Parquet chunks into Raw Store."
        )
        df_out = pl.concat(df_final_chunks, how="diagonal") if df_final_chunks else pl.DataFrame()
        return df_out, injected_files
