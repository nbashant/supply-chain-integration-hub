from __future__ import annotations

import argparse
import json
import re
import tempfile
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as sf
from pyspark.sql.types import (
    DateType,
    DoubleType,
    StringType,
    StructField,
    StructType,
)
from s3_io import PipelineObjectStore

RAW_SCHEMA = StructType(
    [
        StructField("event_date", DateType(), nullable=False),
        StructField("supplier_code", StringType(), nullable=False),
        StructField("product_sku", StringType(), nullable=False),
        StructField("warehouse_code", StringType(), nullable=False),
        StructField("on_hand_quantity", DoubleType(), nullable=False),
        StructField("reserved_quantity", DoubleType(), nullable=False),
        StructField("inbound_quantity", DoubleType(), nullable=False),
        StructField("forecast_quantity", DoubleType(), nullable=False),
        StructField("actual_demand_quantity", DoubleType(), nullable=False),
    ]
)
KEY_COLUMNS = [
    "event_date",
    "supplier_code",
    "product_sku",
    "warehouse_code",
]
QUANTITY_COLUMNS = [
    "on_hand_quantity",
    "reserved_quantity",
    "inbound_quantity",
    "forecast_quantity",
    "actual_demand_quantity",
]


def _safe_run_id(run_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)[:180]


def _source_prefix(partition_date: date) -> str:
    return f"raw/history/inventory/event_date={partition_date.isoformat()}/"


def _manifest_key(partition_date: date, run_id: str) -> str:
    return (
        "manifests/inventory-risk/"
        f"event_date={partition_date.isoformat()}/"
        f"run_id={_safe_run_id(run_id)}.json"
    )


def check_source(partition_date: date) -> dict[str, object]:
    store = PipelineObjectStore()
    keys = store.list_keys(_source_prefix(partition_date))
    if not keys:
        raise RuntimeError(
            f"No raw inventory objects exist for {partition_date.isoformat()}."
        )
    result = {"partition_date": partition_date.isoformat(), "source_keys": keys}
    print(json.dumps(result, indent=2))
    return result


def _invalid_rows(frame: DataFrame) -> DataFrame:
    invalid_key = sf.lit(False)
    for column in KEY_COLUMNS:
        invalid_key = invalid_key | sf.col(column).isNull()
        if column != "event_date":
            invalid_key = invalid_key | (sf.trim(sf.col(column)) == "")
    invalid_quantity = sf.lit(False)
    for column in QUANTITY_COLUMNS:
        invalid_quantity = (
            invalid_quantity | sf.col(column).isNull() | (sf.col(column) < 0)
        )
    return frame.where(invalid_key | invalid_quantity)


def _duplicate_rows(frame: DataFrame) -> DataFrame:
    return frame.groupBy(*KEY_COLUMNS).count().where(sf.col("count") > 1)


def _transform(frame: DataFrame) -> tuple[DataFrame, float, float]:
    available = sf.greatest(
        sf.col("on_hand_quantity") - sf.col("reserved_quantity"),
        sf.lit(0.0),
    )
    transformed = (
        frame.withColumn("available_quantity", available)
        .withColumn(
            "projected_ending_quantity",
            sf.col("available_quantity")
            + sf.col("inbound_quantity")
            - sf.col("forecast_quantity"),
        )
        .withColumn(
            "projected_shortage_quantity",
            sf.greatest(-sf.col("projected_ending_quantity"), sf.lit(0.0)),
        )
        .withColumn(
            "shortage_ratio",
            sf.when(
                sf.col("forecast_quantity") > 0,
                sf.col("projected_shortage_quantity") / sf.col("forecast_quantity"),
            ).otherwise(sf.lit(0.0)),
        )
        .withColumn(
            "forecast_error",
            sf.col("forecast_quantity") - sf.col("actual_demand_quantity"),
        )
        .withColumn("absolute_forecast_error", sf.abs(sf.col("forecast_error")))
    )
    positive = transformed.where(sf.col("shortage_ratio") > 0)
    thresholds = positive.approxQuantile(
        "shortage_ratio",
        [0.5, 0.8],
        0.001,
    )
    low_to_medium, medium_to_high = (
        (float(thresholds[0]), float(thresholds[1])) if thresholds else (0.0, 0.0)
    )
    transformed = transformed.withColumn(
        "severity",
        sf.when(sf.col("shortage_ratio") == 0, sf.lit("none"))
        .when(sf.col("shortage_ratio") <= low_to_medium, sf.lit("low"))
        .when(sf.col("shortage_ratio") <= medium_to_high, sf.lit("medium"))
        .otherwise(sf.lit("high")),
    )
    return transformed, low_to_medium, medium_to_high


def run_pipeline(partition_date: date, run_id: str) -> dict[str, object]:
    store = PipelineObjectStore()
    source = check_source(partition_date)
    safe_run_id = _safe_run_id(run_id)
    with tempfile.TemporaryDirectory(prefix="inventory-pipeline-") as temporary:
        workspace = Path(temporary)
        raw_directory = workspace / "raw"
        curated_directory = workspace / "curated"
        summary_directory = workspace / "summary"
        source_keys = store.download_prefix(
            _source_prefix(partition_date),
            raw_directory,
        )
        spark = (
            SparkSession.builder.master("local[2]")
            .appName(f"inventory-risk-{partition_date.isoformat()}")
            .config("spark.driver.memory", "1g")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.shuffle.partitions", "8")
            .getOrCreate()
        )
        try:
            frame = (
                spark.read.option("header", True)
                .schema(RAW_SCHEMA)
                .csv([str(path) for path in source_keys])
            )
            input_rows = frame.count()
            invalid_rows = _invalid_rows(frame).count()
            duplicate_keys = _duplicate_rows(frame).count()
            quality_report = {
                "partition_date": partition_date.isoformat(),
                "run_id": run_id,
                "input_rows": input_rows,
                "invalid_rows": invalid_rows,
                "duplicate_keys": duplicate_keys,
                "passed": invalid_rows == 0 and duplicate_keys == 0,
            }
            quality_key = (
                "quality/inventory/"
                f"event_date={partition_date.isoformat()}/"
                f"run_id={safe_run_id}.json"
            )
            store.put_bytes(
                quality_key,
                json.dumps(quality_report, indent=2).encode(),
                content_type="application/json",
            )
            if not quality_report["passed"]:
                raise RuntimeError(
                    "Data-quality gates failed: "
                    f"{invalid_rows} invalid rows and "
                    f"{duplicate_keys} duplicate keys."
                )
            transformed, low_to_medium, medium_to_high = _transform(frame)
            transformed.write.mode("overwrite").partitionBy("warehouse_code").parquet(
                str(curated_directory)
            )
            severity_summary = (
                transformed.groupBy("event_date", "severity")
                .agg(
                    sf.count("*").alias("row_count"),
                    sf.sum("projected_shortage_quantity").alias(
                        "projected_shortage_quantity"
                    ),
                    sf.avg("absolute_forecast_error").alias("mean_absolute_error"),
                )
                .orderBy("event_date", "severity")
            )
            severity_summary.write.mode("overwrite").parquet(str(summary_directory))
            curated_prefix = (
                "curated/inventory-risk/"
                f"event_date={partition_date.isoformat()}/"
                f"run_id={safe_run_id}"
            )
            summary_prefix = (
                "curated/inventory-risk-summary/"
                f"event_date={partition_date.isoformat()}/"
                f"run_id={safe_run_id}"
            )
            curated_keys = store.upload_directory(
                curated_directory,
                curated_prefix,
            )
            summary_keys = store.upload_directory(
                summary_directory,
                summary_prefix,
            )
            manifest = {
                "status": "succeeded",
                "partition_date": partition_date.isoformat(),
                "run_id": run_id,
                "created_at": datetime.now(UTC).isoformat(),
                "source_keys": source["source_keys"],
                "input_rows": input_rows,
                "quality_report_key": quality_key,
                "curated_keys": curated_keys,
                "summary_keys": summary_keys,
                "thresholds": {
                    "low_to_medium": low_to_medium,
                    "medium_to_high": medium_to_high,
                    "method": "positive shortage-ratio approximate p50 and p80",
                },
                "spark_version": spark.version,
                "partition_columns": ["event_date", "warehouse_code"],
            }
            manifest_content = json.dumps(manifest, indent=2).encode()
            store.put_bytes(
                _manifest_key(partition_date, run_id),
                manifest_content,
                content_type="application/json",
            )
            store.put_bytes(
                (
                    "manifests/inventory-risk/"
                    f"event_date={partition_date.isoformat()}/latest.json"
                ),
                manifest_content,
                content_type="application/json",
            )
            print(json.dumps(manifest, indent=2))
            return manifest
        finally:
            spark.stop()


def verify_manifest(partition_date: date, run_id: str) -> dict[str, object]:
    store = PipelineObjectStore()
    key = _manifest_key(partition_date, run_id)
    manifest = json.loads(store.get_bytes(key))
    if manifest.get("status") != "succeeded":
        raise RuntimeError(f"Manifest '{key}' is not successful.")
    curated_keys = manifest.get("curated_keys", [])
    summary_keys = manifest.get("summary_keys", [])
    if not any(str(key).endswith(".parquet") for key in curated_keys) or not any(
        str(key).endswith(".parquet") for key in summary_keys
    ):
        raise RuntimeError(f"Manifest '{key}' has no published Parquet objects.")
    print(json.dumps(manifest, indent=2))
    return manifest


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a curated inventory-risk Parquet partition."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("check-source", "run", "verify"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument(
            "--partition-date",
            type=date.fromisoformat,
            required=True,
        )
        if command != "check-source":
            command_parser.add_argument("--run-id", required=True)
    options = parser.parse_args(arguments)
    if options.command == "check-source":
        check_source(options.partition_date)
    elif options.command == "run":
        run_pipeline(options.partition_date, options.run_id)
    else:
        verify_manifest(options.partition_date, options.run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
