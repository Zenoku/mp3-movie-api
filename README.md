# Overview
This FastAPI application lets a user upload a CSV of movies, store it in SQLite, clean it with a configurable processing pipeline, and read it back through a cached endpoint. main.py defines the routes and wires the pieces together. src/storage.py handles all SQL work, with src/database.py creating the movies table and opening connections. src/cache.py keeps recent GET /movies responses in an in-memory FakeRedis store for 90 seconds, keyed by limit. The data_pipeline package validates the data, removes duplicates, handles missing values and removes outliers, and produces a cleaning report. When a CSV is uploaded, POST /upload checks the columns and rows, replaces the stored movies with storage.save(), and clears the cache. GET /movies returns a cached response when one exists and otherwise reads from SQL, caches the result, and returns it. POST /movies/process loads the stored movies, runs the pipeline, saves the cleaned rows back to SQLite, and invalidates the cache so the next read shows the cleaned data.

# Run the api
```bash
python -m uvicorn main:app --reload
```

# Run the tests
```bash
python -m pytest tests -v
```

# Sample Processing Request
1. Start api using `python -m uvicorn main:app --reload`
2. Open http://127.0.0.1:8000/docs
3. Upload `fixtures/sample_movies.csv` to POST /upload
4. Run POST movies/process with the following JSON
```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

# Expected Result
Response body from processing:
```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```
