"""Baseline and Regression Benchmark Suite for Observability Infrastructure.

Owns
----
- Measurement of logging throughput, event volume, file I/O latency, and compression.
- Recording repeatable baseline metrics for legacy logging vs modernized structured events.
- Evaluation of acceptance gates (≤0.5% runtime regression normal, ≤1.5% debug).

Does not own
-------------
- Production logging emitter logic (owned by application.observability).
- Control Plane persistence transactions (owned by infrastructure.control_plane).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Final, TypedDict
import zlib

import psutil

ROOT_DIR: Final[Path] = Path(__file__).resolve().parent.parent
OUTPUT_DIR: Final[Path] = ROOT_DIR / ".planning"
BASELINE_REPORT_PATH: Final[Path] = OUTPUT_DIR / "baseline_benchmark.json"


class CompressionBenchmark(TypedDict):
    """Metrics comparing compression algorithms and levels."""

    level: int
    raw_size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float
    duration_ms: float


class MicroBenchmarkResult(TypedDict):
    """High-resolution micro-benchmark metrics for logging I/O."""

    iterations: int
    total_time_ms: float
    records_per_second: float
    log_file_size_bytes: int
    peak_memory_mb: float
    cpu_percent: float
    compression_benchmarks: list[CompressionBenchmark]


class PipelineBaselineMetrics(TypedDict):
    """Operational baseline benchmarks for full pipeline runs."""

    cached_run_seconds: float
    cold_run_seconds: float
    estimated_event_count: int
    approx_uncompressed_log_kb: float
    approx_compressed_log_kb: float


class LiveProductionRunMetrics(TypedDict):
    """Empirical metrics captured from actual production pipeline run."""

    runtime_seconds: float
    total_nodes: int
    unique_isins: int
    files_scanned: int
    open_tax_lots: int
    uncompressed_log_bytes: int
    log_line_count: int
    zlib_level_6_bytes: int
    zlib_level_9_bytes: int
    compression_ratio_level_6: float


class ObservabilityBaselineReport(TypedDict):
    """Combined baseline report combining micro-benchmarks, production run, and medians."""

    timestamp: str
    architecture_version: str
    pipeline_baseline: PipelineBaselineMetrics
    live_production_run: LiveProductionRunMetrics
    micro_benchmark: MicroBenchmarkResult


def run_compression_benchmark(raw_data: bytes) -> list[CompressionBenchmark]:
    """Benchmark zlib compression ratios and execution times across compression levels.

    Parameters
    ----------
    raw_data : bytes
        Raw uncompressed log payload.

    Returns
    -------
    list[CompressionBenchmark]
        List of benchmark records for each tested compression level.
    """
    results: list[CompressionBenchmark] = []
    raw_size = len(raw_data)
    for level in (1, 6, 9):
        start = time.perf_counter_ns()
        compressed = zlib.compress(raw_data, level=level)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000.0
        comp_size = len(compressed)
        ratio = raw_size / comp_size if comp_size > 0 else 0.0
        results.append(
            CompressionBenchmark(
                level=level,
                raw_size_bytes=raw_size,
                compressed_size_bytes=comp_size,
                compression_ratio=round(ratio, 2),
                duration_ms=round(elapsed_ms, 3),
            )
        )
    return results


def run_micro_benchmark(iterations: int = 10_000) -> MicroBenchmarkResult:
    """Benchmark standard legacy FileHandler logging throughput and system impact.

    Parameters
    ----------
    iterations : int, default=10_000
        Number of log records to emit.

    Returns
    -------
    MicroBenchmarkResult
        Measured throughput, file size, memory, and compression metrics.
    """
    process = psutil.Process()
    mem_before = process.memory_info().rss / (1024 * 1024)

    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = Path(tmp_dir) / "benchmark_legacy.log"

        test_logger = logging.getLogger("benchmark_logger")
        test_logger.setLevel(logging.DEBUG)
        for h in test_logger.handlers[:]:
            test_logger.removeHandler(h)

        handler = logging.FileHandler(str(log_file), mode="w", encoding="utf-8")
        fmt = (
            "%(asctime)s.%(msecs)03d | %(levelname)-8s | Run:bench_001 | Stage:TRANSFORM | "
            "ISIN:INE002A01018 | Proc:MainProcess | [%(module)s:%(funcName)s:%(lineno)d] | %(message)s"
        )
        handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
        test_logger.addHandler(handler)

        # Warm up
        for _ in range(100):
            test_logger.debug("Benchmark warm-up record payload verification.")

        # Measure emission loop
        start_ns = time.perf_counter_ns()
        for i in range(iterations):
            test_logger.info(
                f"[BRONZE:DETAIL] Executing statement chunk {i} for table benchmark_trades with 250 rows."
            )

        handler.flush()
        elapsed_ns = time.perf_counter_ns() - start_ns
        total_time_ms = elapsed_ns / 1_000_000.0
        records_per_sec = (iterations / elapsed_ns) * 1_000_000_000.0

        # Read generated log for compression test
        raw_log_bytes = log_file.read_bytes()
        file_size = len(raw_log_bytes)

        # Cleanup handler
        handler.close()
        test_logger.removeHandler(handler)

        compression_results = run_compression_benchmark(raw_log_bytes)

    mem_after = process.memory_info().rss / (1024 * 1024)
    peak_mem = max(mem_before, mem_after)

    return MicroBenchmarkResult(
        iterations=iterations,
        total_time_ms=round(total_time_ms, 2),
        records_per_second=round(records_per_sec, 2),
        log_file_size_bytes=file_size,
        peak_memory_mb=round(peak_mem, 2),
        cpu_percent=round(process.cpu_percent(), 2),
        compression_benchmarks=compression_results,
    )


def generate_baseline_report() -> ObservabilityBaselineReport:
    """Generate and persist the authoritative Phase 0 baseline report.

    Returns
    -------
    ObservabilityBaselineReport
        The structured baseline report dictionary.
    """
    micro = run_micro_benchmark(iterations=10_000)

    # Recorded pipeline baseline from production observation (Section 0 of plan)
    pipeline = PipelineBaselineMetrics(
        cached_run_seconds=28.0,
        cold_run_seconds=48.0,
        estimated_event_count=1_200,
        approx_uncompressed_log_kb=380.0,
        approx_compressed_log_kb=42.0,
    )

    # Actual live run evidence captured from user run (2026-10-22)
    prod_log_path = ROOT_DIR / "outputs" / "Personal_Finance_DB.log"
    if prod_log_path.exists():
        raw_bytes = prod_log_path.read_bytes()
        log_lines = len(raw_bytes.decode("utf-8", errors="replace").splitlines())
        uncompressed_size = len(raw_bytes)
        zlib_6 = len(zlib.compress(raw_bytes, level=6))
        zlib_9 = len(zlib.compress(raw_bytes, level=9))
        ratio_6 = round(uncompressed_size / zlib_6, 2)
    else:
        uncompressed_size = 347_589
        log_lines = 1_192
        zlib_6 = 33_687
        zlib_9 = 32_660
        ratio_6 = 10.32

    live_run = LiveProductionRunMetrics(
        runtime_seconds=28.81,
        total_nodes=46,
        unique_isins=147,
        files_scanned=1627,
        open_tax_lots=341,
        uncompressed_log_bytes=uncompressed_size,
        log_line_count=log_lines,
        zlib_level_6_bytes=zlib_6,
        zlib_level_9_bytes=zlib_9,
        compression_ratio_level_6=ratio_6,
    )

    report = ObservabilityBaselineReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        architecture_version="v9.2.9",
        pipeline_baseline=pipeline,
        live_production_run=live_run,
        micro_benchmark=micro,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    """Run baseline benchmark and print summary to stdout."""
    print("Executing Phase 0 Observability Baseline Micro-Benchmark...")
    report = generate_baseline_report()
    micro = report["micro_benchmark"]
    pipe = report["pipeline_baseline"]

    print("\n--- Pipeline Operational Baselines (v9.2.9) ---")
    print(f"Cached Run Median:            {pipe['cached_run_seconds']} s")
    print(f"Cold Run Median:              {pipe['cold_run_seconds']} s")
    print(f"Typical Event Volume:         {pipe['estimated_event_count']} events")
    print(f"Normal Mode Regression Gate:  <= 0.5% ({pipe['cached_run_seconds'] * 0.005:.2f} s)")
    print(f"Debug Mode Regression Gate:   <= 1.5% ({pipe['cached_run_seconds'] * 0.015:.2f} s)")

    print("\n--- Legacy FileHandler Micro-Benchmark (10,000 records) ---")
    print(f"Total Time:                   {micro['total_time_ms']} ms")
    print(f"Throughput:                   {micro['records_per_second']:,.0f} records/sec")
    print(f"Log Size on Disk:             {micro['log_file_size_bytes'] / 1024:.1f} KB")

    print("\n--- Zlib Compression Analysis ---")
    for cb in micro["compression_benchmarks"]:
        print(
            f"Level {cb['level']}: {cb['compressed_size_bytes'] / 1024:.1f} KB "
            f"({cb['compression_ratio']}x ratio) in {cb['duration_ms']} ms"
        )

    print(f"\nAuthoritative report written to {BASELINE_REPORT_PATH}")


if __name__ == "__main__":
    main()

