# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingImports=false
import concurrent.futures
import io
import time
import uuid
from datetime import date, datetime, timedelta

import polars as pl
import yfinance as yf  # type: ignore[import-untyped]

from personal_finance_etl.backend.load.control_plane import ControlPlane
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class CurrencyExtractor:
    """Extracts daily FX rates from yfinance based on active mapping, with delta fetching and chunking."""

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
            logger.debug(f"[Currency Extractor] Skipping empty ticker {row.get('UID')}")
            return pl.DataFrame(), f"Warning: Skipping empty ticker {row.get('UID')}"

        fetch_start = start_dt - timedelta(days=15)
        if max_cached_date and max_cached_date >= fetch_start:
            fetch_start = max_cached_date + timedelta(days=1)

        if fetch_start > end_dt:
            logger.debug(
                f"[Currency Extractor] {ticker} fully cached up to {end_dt}. Skipping API fetch."
            )
            return pl.DataFrame(), f"✓ {ticker} fully cached up to {end_dt}"

        logger.debug(f"[Currency Extractor] API Fetching {ticker} from {fetch_start} to {end_dt}")
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
                    f"[Currency Extractor] Attempt {attempt + 1}/3 failed for {ticker}: {e}"
                )
                if attempt == 2:
                    return pl.DataFrame(), f"Error on {ticker}: {str(e)}"
                time.sleep(1 + attempt * 2)

        if hist_pd is None or hist_pd.empty:
            logger.debug(f"[Currency Extractor] No data returned from API for {ticker}.")
            return pl.DataFrame(), f"⚠ No new data fetched for {ticker}"

        hist_pd.index = hist_pd.index.tz_localize(None).normalize()  # pyright: ignore
        hist_pl = pl.from_pandas(hist_pd.reset_index())

        if "Date" not in hist_pl.columns:
            hist_pl = hist_pl.rename({"index": "Date"})

        df_api = hist_pl.select([pl.col("Date").cast(pl.Date), pl.col("Close").cast(pl.Float64)])

        # Create a continuous spine to handle closures (weekends/holidays) without re-fetching
        df_spine = pl.DataFrame(
            {"Date": pl.date_range(start=fetch_start, end=end_dt, interval="1d", eager=True)}
        )

        df_new = df_spine.join(df_api, on="Date", how="left")

        df_new = df_new.with_columns(
            pl.lit(row["UID"]).alias("Currency_ID"),
            pl.lit(row["CURRENCY_NAME"]).alias("Currency_Name"),
            pl.lit(row["ISO"]).alias("Currency_Code"),
            pl.lit(row["Target_Currency_Code"]).alias("Target_Currency_Code"),
            pl.lit(ticker).alias("yF_Ticker"),
            pl.col("Close").alias("FX_Rate"),
            pl.lit("Yahoo Finance").alias("Data_Provider"),
            pl.lit(datetime.now().isoformat()).alias("Extraction_Time"),
            pl.lit(fetch_start).alias("Requested_Start"),
            pl.lit(end_dt).alias("Requested_End"),
            pl.col("Close").is_null().alias("Is_Closure_Gap"),
        ).drop("Close")

        logger.debug(
            f"[Currency Extractor] Parsed {df_new.height} records (including gaps) for {ticker}."
        )

        msg = f"✓ API Fetched {ticker} ({fetch_start} to {end_dt}) - {df_new.height} rows"

        return df_new, msg

    def extract_currency_delta(
        self,
        df_currency: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
        df_bronze_cached: pl.DataFrame,
    ) -> tuple[pl.DataFrame, list[str]]:

        df_active = df_currency.filter(pl.col("Is_Active"))

        tickers_df = df_active.to_dicts()
        total = len(tickers_df)
        all_new_data: list[pl.DataFrame] = []

        cache_map: dict[str, date] = {}
        if not df_bronze_cached.is_empty():
            aggs = df_bronze_cached.group_by("yF_Ticker").agg(pl.max("Date").alias("MaxDate"))
            for r in aggs.to_dicts():
                cache_map[r["yF_Ticker"]] = r["MaxDate"]

        self.status_queue.put(
            EngineStatus(
                msg=f"Starting Currency FX extractor for {total} tickers...",
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

        df_combined = pl.concat(all_new_data, how="diagonal_relaxed")
        df_combined = df_combined.with_columns(pl.col("Date").dt.year().alias("Year"))

        years = df_combined["Year"].unique().to_list()
        injected_files: list[str] = []
        df_final_chunks: list[pl.DataFrame] = []

        for year in years:
            df_year = df_combined.filter(pl.col("Year") == year).drop("Year")

            buf = io.BytesIO()
            df_year.write_parquet(buf)
            raw_bytes = buf.getvalue()

            run_uuid = str(uuid.uuid4())[:8]
            filename = f"currency_delta_{year}_{run_uuid}.parquet"
            virtual_path = self.cp.artifacts.inject_virtual_file(
                filename=filename, category="currency_history", raw_bytes=raw_bytes
            )
            injected_files.append(virtual_path)

            df_final_chunks.append(
                df_year.with_columns(
                    pl.lit(filename).alias("__file_name__"),
                    pl.lit(virtual_path).alias("__folder_path__"),
                )
            )

        logger.info(
            f"Currency Extractor injected {len(injected_files)} Parquet chunks into Raw Store."
        )
        df_out = (
            pl.concat(df_final_chunks, how="diagonal_relaxed")
            if df_final_chunks
            else pl.DataFrame()
        )
        return df_out, injected_files
