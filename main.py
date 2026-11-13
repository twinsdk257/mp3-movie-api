import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import (
    HealthResponse,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    MovieStorage,
    MovieCache,
    ProcessConfig,
    setup_logging,
)
from src.storage import MOVIE_COLUMNS
from data_pipeline import create_cleaning_report, process_data, validate_dataframe

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Movie API", version="1.0.0")
storage = MovieStorage()
cache = MovieCache()

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    # TODO 1: Keep MP2's .csv check, await file.read(), and CSV parsing.
    # Raise HTTPException with status 400 for an unsupported extension or an expected parsing failure.

    # TODO 2: Quick validation before saving:
    # Require exactly MOVIE_COLUMNS
    # Require at least one data row (hint: Use if df.empty: to check for an empty DataFrame).
    # Raise HTTPException with status 400 if these checks fail.
    # Reorder the columns to match MOVIE_COLUMNS.

    # TODO 3: Call storage.save(df) to replace the current collection.
    # Log the filename and saved row count at INFO.
    # Return filename, rows, columns, and column_names for this upload.
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ".csv":
        logger.warning("Unsupported file format: %s", Path(filename).suffix)
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported."
        )

    contents = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError
    ):
        logger.warning("Unable to read CSV file: %s", filename)
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty or is not a valid readable CSV."
        )

    if set(df.columns) != set(MOVIE_COLUMNS) or len(df.columns) != len(MOVIE_COLUMNS):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain exactly these columns: {MOVIE_COLUMNS}"
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="The uploaded CSV must contain at least one movie."
        )

    df = df[MOVIE_COLUMNS]
    storage.save(df)
    cache.invalidate()

    logger.info(
        "Uploaded movie collection: filename=%s, rows=%s",
        filename,
        len(df)
    )

    return {
        "filename": filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns)
    }

@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    # TODO 1: Look up the response using cache.get(limit).
    # If it is not None, log the cache hit at INFO and return it.
    # Keep Part 1's SQL retrieval, total count, and response construction here.
    # TODO 2: Before the existing return, cache the complete response
    # using cache.set(limit, response).
    # Keep the existing row-count log and return.
    cached_response = cache.get(limit)

    if cached_response is not None:
        logger.info("Returning cached movies: limit=%s", limit)
        return cached_response

    records = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()

    response = {
        "data": records,
        "total_rows": total_rows
    }

    cache.set(limit, response)

    logger.info("Retrieved movie collection: rows=%s", total_rows)

    return response

@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    # TODO 1: Retrieve data using storage.get().
    # Raise HTTPException with status 400 if empty.

    # TODO 2: Reuse MP2's configuration, validation, processing,
    # cleaning report, logging, and ValueError handling.

    # TODO 3: Save the processed DataFrame using storage.save().
    # Return validation_rows_removed and cleaning_report without a dataset ID.
    df = storage.get()

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No movies available to process."
        )

    config_dict = config.model_dump()

    numeric_columns = config_dict["validation"]["numeric_columns"]

    missing_columns = [
        column
        for column in numeric_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Numeric columns not found: {missing_columns}"
        )

    try:
        validation_settings = config_dict["validation"]

        validated_df = validate_dataframe(
            df,
            required_columns=validation_settings["required_columns"],
            numeric_columns=validation_settings["numeric_columns"],
        )

        validation_rows_removed = len(df) - len(validated_df)
        validated_copy = validated_df.copy()

        processed_df = process_data(
            validated_df,
            config_dict,
        )

        cleaning_report = create_cleaning_report(
            validated_copy,
            processed_df,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    storage.save(processed_df)
    cache.invalidate()

    logger.info(
        "Processed movies: validation_removed=%s, "
        "rows_before=%s, rows_after=%s",
        validation_rows_removed,
        len(validated_copy),
        len(processed_df),
    )

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }

@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    # TODO: Call storage.query_movies(columns, min_rating, limit).
    # Catch ValueError and raise HTTPException with status 400.
    # Return id plus the selected fields, or [] if there are no matches.
    # Log the selected columns and returned row count at INFO.
    """Search movies by rating and selected columns."""
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    logger.info(
        "Searched movies: columns=%s, returned_rows=%s",
        columns,
        len(results)
    )

    return results