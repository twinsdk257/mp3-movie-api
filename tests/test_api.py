import pytest

from src import MovieStorage
import main

def test_movies_persist(client, test_storage, uploaded_movies):
    # TODO: create another MovieStorage pointing to test_storage.db_path.
    # Use that object to get the movies and count them.
    # Check 20 rows, all four DataFrame columns, and the original title order.
    # Compare IDs from that object's select_columns() with GET /movies? limit=100.
    # Both should return IDs 1 through 20 in row order.
    reloaded_storage = MovieStorage(test_storage.db_path)

    movies_df = reloaded_storage.get()

    assert len(movies_df) == 20
    assert list(movies_df.columns) == [
        "title", "release_year", "rating", "genre"
    ]

    expected_titles = [
        "Movie A", "Movie B", "Movie B", "Movie C",
        "Movie D", "Movie D", "Movie E", "Movie F",
        "Movie G", "Movie H", "Movie I", "Movie J",
        "Movie K", "Movie L", "Movie M", "Movie N",
        "Movie O", "Movie P", "Movie Q", "Movie R"
    ]

    assert movies_df["title"].tolist() == expected_titles

    database_records = reloaded_storage.select_columns(
        ["title"], limit=100
    )
    api_response = client.get("/movies?limit=100")

    assert api_response.status_code == 200

    database_ids = [record["id"] for record in database_records]
    api_ids = [record["id"] for record in api_response.json()["data"]]

    assert database_ids == list(range(1, 21))
    assert api_ids == database_ids

def test_cache_and_processing(client, uploaded_movies, processing_body):
    # TODO 1: GET /movies with limits 100 and 1.
    # Check 200 and that main.cache.get(limit) equals each response body.
    # TODO 2: repeat limit=100 and check the same response.
    # TODO 3: POST /movies/process using json=processing_body.
    # Check 200, zero validation removals, and the 20 -> 16 cleaning report.
    # Confirm both old cache entries are None.
    # TODO 4: retrieve again; check total_rows=16 and titles Movie A through Movie P, in order.
    # Check IDs 1 through 16 in the retrieved records.
    # Check that the new response is cached.
    response_100 = client.get("/movies?limit=100")
    response_1 = client.get("/movies?limit=1")

    assert response_100.status_code == 200
    assert response_1.status_code == 200

    assert main.cache.get(100) == response_100.json()
    assert main.cache.get(1) == response_1.json()

    repeated_response = client.get("/movies?limit=100")

    assert repeated_response.status_code == 200
    assert repeated_response.json() == response_100.json()

    process_response = client.post(
        "/movies/process",
        json=processing_body
    )

    assert process_response.status_code == 200

    process_data = process_response.json()

    assert process_data["validation_rows_removed"] == 0
    assert process_data["cleaning_report"]["rows_before"] == 20
    assert process_data["cleaning_report"]["rows_after"] == 16
    assert process_data["cleaning_report"]["rows_removed"] == 4

    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    updated_response = client.get("/movies?limit=100")

    assert updated_response.status_code == 200

    updated_data = updated_response.json()

    assert updated_data["total_rows"] == 16
    assert len(updated_data["data"]) == 16

    expected_titles = [
        f"Movie {letter}" for letter in "ABCDEFGHIJKLMNOP"
    ]

    actual_titles = [
        movie["title"] for movie in updated_data["data"]
    ]

    actual_ids = [
        movie["id"] for movie in updated_data["data"]
    ]

    assert actual_titles == expected_titles
    assert actual_ids == list(range(1, 17))

    assert main.cache.get(100) == updated_data

def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    # TODO 1: GET /movies with limit=100 to populate the cache.
    # Assert 200 and keep the response for comparison.
    # TODO 2: Use monkeypatch to replace main.storage.select_columns()
    # and main.storage.count_movies() with a function that fails the test
    # if either method is called.
    # TODO 3: Repeat the same GET request.
    # Assert 200 and the same response body as the first request.
    first_response = client.get("/movies?limit=100")

    assert first_response.status_code == 200
    first_data = first_response.json()

    def fail_if_called(*args, **kwargs):
        pytest.fail("Database retrieval should be skipped on a cache hit")

    monkeypatch.setattr(
        main.storage, "select_columns", fail_if_called
    )
    monkeypatch.setattr(
        main.storage, "count_movies", fail_if_called
    )

    second_response = client.get("/movies?limit=100")

    assert second_response.status_code == 200
    assert second_response.json() == first_data
