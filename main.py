import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import DatasetInfo, DatasetStorage, HealthResponse, setup_logging
from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import ProcessConfig, ProcessingReport

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
storage = DatasetStorage()

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload", response_model=DatasetInfo)
async def upload_dataset(file: UploadFile = File(...)):
    """Read and store a CSV upload."""
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

    dataset_id = storage.save(df, filename)
    metadata = storage.get_metadata(dataset_id)

    logger.info(
        "Uploaded dataset: id=%s, filename=%s, rows=%s",
        dataset_id,
        filename,
        len(df)
    )

    return metadata

@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, limit: int = Query(default=100, ge=1)):
    """Return up to limit rows from a stored dataset."""
    metadata = storage.get_metadata(dataset_id)

    if metadata is None:
        logger.warning("Dataset not found: id=%s", dataset_id)
        raise HTTPException(
            status_code=404,
            detail=f"Dataset with ID {dataset_id} not found."
        )

    df = storage.get(dataset_id)

    records = df.head(limit).to_dict(orient="records")

    return {
        "id": dataset_id,
        "filename": metadata["filename"],
        "total_rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "records": records
    }

@app.post(
    "/datasets/{dataset_id}/process",
    response_model=ProcessingReport
)
def process_dataset(dataset_id: int, config: ProcessConfig):
    """Validate and process a stored dataset using MP1 functions."""
    # TODO: retrieve, validate, process, report, update, and return.
    # 1. Retrieve
    df = storage.get(dataset_id)

    if df is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        )

    # 2. Convert
    config_dict = config.model_dump()

    # 3. Check numeric columns
    numeric_columns = config_dict["validation"]["numeric_columns"]

    missing_columns = [
        column
        for column in numeric_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Numeric columns not found: {missing_columns}",
        )

    try:
        # 4. Validate data
        validation_settings = config_dict["validation"]

        validated_df = validate_dataframe(
            df,
            required_columns=validation_settings["required_columns"],
            numeric_columns=validation_settings["numeric_columns"],
        )

        # 5. Count rows
        validation_rows_removed = len(df) - len(validated_df)
        validated_copy = validated_df.copy()

        # 6. Process validated data
        processed_df = process_data(
            validated_df,
            config_dict,
        )

        # 7. Create cleaning report
        cleaning_report = create_cleaning_report(
            validated_copy,
            processed_df,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    # 8. Update storage
    storage.update(dataset_id, processed_df)

    # 9. Return response
    logger.info(
        "Processed dataset: id=%s, validation_removed=%s, "
        "rows_before=%s, rows_after=%s",
        dataset_id,
        validation_rows_removed,
        len(validated_copy),
        len(processed_df),
    )

    return {
        "id": dataset_id,
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }
