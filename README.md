# Movie API

This project is a FastAPI application for uploading, storing, processing, and retrieving movie data. The `main.py` module defines the API endpoints, while `src/storage.py` manages persistent movie records using SQLite. The `src/models.py` module defines the request and response models used by the API. Movie data can be uploaded through the `/upload` endpoint and processed through `/movies/process`, which validates and cleans the data before saving the updated collection. The `src/cache.py` module uses FakeRedis to cache responses from `GET /movies` for 90 seconds, reducing repeated database queries. Cached responses are invalidated after successful uploads or processing so that retrievals always reflect the latest stored data. The `tests/` directory contains automated tests that verify persistence, cache invalidation, and cache hits.

## Running the API

```bash
python -m uvicorn main:app --reload


cat > README.md <<'EOF'
# Movie API

This project is a FastAPI application for uploading, storing, processing, and retrieving movie data. The `main.py` module defines the API endpoints, while `src/storage.py` manages persistent movie records using SQLite. The `src/models.py` module defines the request and response models used by the API. Movie data is uploaded through `/upload` and saved to the SQLite database. The `/movies/process` endpoint validates and cleans the uploaded data before saving the updated collection. The `src/cache.py` module uses FakeRedis to cache `GET /movies` responses for 90 seconds, reducing repeated database queries. The cache is invalidated after successful uploads or processing so that retrievals reflect the latest stored data.

## Running the API

```bash
python -m uvicorn main:app --reload
```

## Running Tests

```bash
python -m pytest tests -v
```

## Sample Processing Request

Send a POST request to `/movies/process` with:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {
      "enabled": true,
      "axis": "rows"
    },
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

Expected result for the provided 20-row sample:

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
