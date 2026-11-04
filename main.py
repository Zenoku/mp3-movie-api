import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import (
    DatasetInfo,
    HealthResponse,
    ProcessConfig,
    ProcessingReport,
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    log_requests,
    setup_logging
)
from src.storage import MOVIE_COLUMNS
from data_pipeline import create_cleaning_report, process_data, validate_dataframe

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    # TODO 1: Keep MP2's .csv check, await file.read(), and CSV parsing.
    # Raise HTTPException with status 400 for an unsupported extension or an expected parsing failure.
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ".csv":
        logger.warning(f"Rejected non-CSV upload: {filename}")
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    contents = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except pd.errors.EmptyDataError:
        logger.warning(f"Empty CSV uploaded {filename}")
        raise HTTPException(status_code=400, detail="The CSV file is empty")
    except pd.errors.ParserError:
        logger.warning(f"Could not parse CSV {filename}")
        raise HTTPException(status_code=400, detail="This file is not a valid CSV")
    except UnicodeDecodeError:
        logger.warning(f"Could not decode CSV {filename}")
        raise HTTPException(status_code=400, detail="The file could not be decoded")


    # TODO 2: Quick validation before saving:
    # Require exactly MOVIE_COLUMNS
    # Require at least one data row (hint: Use if df.empty: to check for an empty DataFrame).
    # Raise HTTPException with status 400 if these checks fail.
    # Reorder the columns to match MOVIE_COLUMNS.
    if sorted(df.columns) != sorted(MOVIE_COLUMNS):
        logger.warning(f"Invalid columns in {filename}: {list(df.columns)}")
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain exactly these columns: {MOVIE_COLUMNS}",
        )

    if df.empty:
        logger.warning(f"No data rows in {filename}")
        raise HTTPException(status_code=400, detail="The CSV has no data rows")

    df = df[MOVIE_COLUMNS]

    # TODO 3: Call storage.save(df) to replace the current collection.
    # Log the filename and saved row count at INFO.
    # Return filename, rows, columns, and column_names for this upload.
    storage.save(df)
    logger.info(f"Uploaded movies: filename={filename}, rows={len(df)}")

    return {
        "filename": filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
    }

@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    # TODO: Use MovieStorage methods to retrieve up to limit rows and count the total number of stored movies.
    # Return {"data": ..., "total_rows": ...}.
    # If empty, return {"data": [], "total_rows": 0}.
    # Log the row count at INFO.
    total_rows = storage.count_movies()

    if total_rows == 0:
        logger.info("Returning 0 movie rows")
        return {"data": [], "total_rows": 0}

    data = storage.select_columns(MOVIE_COLUMNS, limit=limit)
    logger.info(f"Returning {len(data)} of {total_rows} movie rows")
    return {"data": data, "total_rows": total_rows}

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
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        logger.warning(f"Invalid movie search: {error}")
        raise HTTPException(status_code=400, detail=str(error))

    logger.info(
        f"Queried movies: columns={columns}, min_rating={min_rating}, returned_rows={len(results)}"
    )
    return results

@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    # TODO 1: Retrieve data using storage.get().
    # Raise HTTPException with status 400 if empty.
    df = storage.get()
    if df.empty:
        logger.warning("Process requested but no movies are stored")
        raise HTTPException(status_code=400, detail="No movies stored; upload a CSV first")

    # TODO 2: Reuse MP2's configuration, validation, processing,
    # cleaning report, logging, and ValueError handling.
    config_dict = config.model_dump()
    required_columns = config_dict["validation"]["required_columns"]
    numeric_columns = config_dict["validation"]["numeric_columns"]

    missing = [col for col in numeric_columns if col not in df.columns]
    if missing:
        logger.warning(f"Movies: missing numeric columns {missing}")
        raise HTTPException(status_code=400, detail=f"Numeric columns not found in movies: {missing}")

    try:
        validated_df = validate_dataframe(df, required_columns, numeric_columns)

        validation_rows_removed = len(df) - len(validated_df)
        validated_copy = validated_df.copy()
        logger.info(f"Movies: validation removed {validation_rows_removed} rows, {len(validated_df)} remaining")

        processed_df = process_data(validated_df, config_dict)

        cleaning_report = create_cleaning_report(validated_copy, processed_df)
        logger.info(f"Movies: processing report {cleaning_report}")
    except ValueError as error:
        logger.warning(f"Movies: processing failed: {error}")
        raise HTTPException(status_code=400, detail=str(error))

    # TODO 3: Save the processed DataFrame using storage.save().
    # Return validation_rows_removed and cleaning_report without a dataset ID.
    storage.save(processed_df)
    logger.info(f"Movies: stored {len(processed_df)} processed rows")

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }
