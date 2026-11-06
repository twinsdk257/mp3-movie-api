# data_processor.py
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def remove_duplicates(df):
    """Remove duplicate rows."""
    rows_before = len(df)
    df = df.drop_duplicates()
    rows_removed = rows_before - len(df)

    logger.debug(
        "remove_duplicates: %s → %s rows",
        rows_before,
        len(df)
    )

    return df


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        before = len(df)
        df = df.dropna(axis=0)
        removed = before - len(df)

    elif axis == "columns":
        before = len(df.columns)
        df = df.dropna(axis=1)
        removed = before - len(df.columns)

    else:
        logger.error("Unsupported missing-value axis: %s", axis)
        raise ValueError(f"Unsupported axis: {axis}")

    logger.debug("handle_missing: removed %s %s", removed, axis)
    return df


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    if method not in ("iqr", "zscore"):
        logger.error("Unsupported outlier method: %s", method)
        raise ValueError(f"Unsupported outlier method: {method}")

    for column in columns:
        if column not in df.columns:
            logger.warning("Column not found: %s", column)
            continue

        if not pd.api.types.is_numeric_dtype(df[column]):
            logger.warning("Column is not numeric: %s", column)
            continue

        before = len(df)

        if method == "iqr":
            q1 = df[column].quantile(0.25)
            q3 = df[column].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr

            df = df[
                (df[column] >= lower) &
                (df[column] <= upper)
            ]

            logger.debug(
                "%s: lower=%s, upper=%s, removed=%s",
                column, lower, upper, before - len(df)
            )

        elif method == "zscore":
            mean = df[column].mean()
            std = df[column].std()

            if std == 0:
                logger.debug(
                    "%s: standard deviation is zero; no outliers removed",
                    column
                )
                continue

            zscores = (df[column] - mean) / std
            df = df[zscores.abs() <= threshold]

            logger.debug(
                "%s: method=%s, threshold=%s, removed=%s",
                column, method, threshold, before - len(df)
            )

    return df


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    settings = config["processing"]

    if settings["remove_duplicates"]:
        df = remove_duplicates(df)

    missing = settings["missing"]
    if missing["enabled"]:
        df = handle_missing(df, missing["axis"])

    outliers = settings["outliers"]
    if outliers["enabled"]:
        df = remove_outliers(
            df,
            outliers["columns"],
            outliers["method"],
            outliers["threshold"]
        )

    return df


def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    return {
        "rows_before": len(df_before),
        "rows_after": len(df_after),
        "rows_removed": len(df_before) - len(df_after),
        "columns_before": len(df_before.columns),
        "columns_after": len(df_after.columns),
        "columns_removed": (
            len(df_before.columns) - len(df_after.columns)
        )
    }
