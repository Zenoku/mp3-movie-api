import pytest

from src import MovieStorage
import main

def test_movies_persist(client, test_storage, uploaded_movies):
    # TODO: create another MovieStorage pointing to test_storage.db_path.
    # Use that object to get the movies and count them.
    other = MovieStorage(test_storage.db_path)
    df = other.get()

    # Check 20 rows, all four DataFrame columns, and the original title order.
    assert len(df) == 20
    assert other.count_movies() == 20
    assert list(df.columns) == main.MOVIE_COLUMNS

    with open("fixtures/sample_movies.csv", encoding="utf-8") as f:
        original_titles = [line.split(",")[0] for line in f.read().splitlines()[1:]]
    assert df["title"].tolist() == original_titles

    # Compare IDs from that object's select_columns() with GET /movies?limit=100.
    # Both should return IDs 1 through 20 in row order.
    stored_ids = [row["id"] for row in other.select_columns(main.MOVIE_COLUMNS, limit=100)]
    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    api_ids = [row["id"] for row in response.json()["data"]]

    assert stored_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    # TODO 1: GET /movies with limits 100 and 1.
    # Check 200 and that main.cache.get(limit) equals each response body.
    full = client.get("/movies", params={"limit": 100})
    assert full.status_code == 200
    assert main.cache.get(100) == full.json()

    one = client.get("/movies", params={"limit": 1})
    assert one.status_code == 200
    assert main.cache.get(1) == one.json()
    assert len(one.json()["data"]) == 1

    # TODO 2: repeat limit=100 and check the same response.
    repeat = client.get("/movies", params={"limit": 100})
    assert repeat.status_code == 200
    assert repeat.json() == full.json()
    assert main.cache.get(100) == repeat.json()

    # TODO 3: POST /movies/process using json=processing_body.
    # Check 200, zero validation removals, and the 20 -> 16 cleaning report.
    # Confirm both old cache entries are None.
    processed = client.post("/movies/process", json=processing_body)
    assert processed.status_code == 200
    body = processed.json()
    assert body["validation_rows_removed"] == 0
    report = body["cleaning_report"]
    assert 20 in report.values() and 16 in report.values()  # see note 1
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    # TODO 4: retrieve again; check total_rows=16 and titles Movie A through Movie P, in order.
    # Check IDs 1 through 16 in the retrieved records.
    # Check that the new response is cached.
    after = client.get("/movies", params={"limit": 100})
    assert after.status_code == 200
    result = after.json()
    assert result["total_rows"] == 16
    assert [m["title"] for m in result["data"]] == [f"Movie {c}" for c in "ABCDEFGHIJKLMNOP"]
    assert [m["id"] for m in result["data"]] == list(range(1, 17))
    assert main.cache.get(100) == result


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    # TODO 1: GET /movies with limit=100 to populate the cache.
    # Assert 200 and keep the response for comparison.
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200

    # TODO 2: Use monkeypatch to replace main.storage.select_columns()
    # and main.storage.count_movies() with a function that fails the test
    # if either method is called.
    def fail(*args, **kwargs):
        raise AssertionError("database was accessed on a cache hit")

    monkeypatch.setattr(main.storage, "select_columns", fail)
    monkeypatch.setattr(main.storage, "count_movies", fail)

    # TODO 3: Repeat the same GET request.
    # Assert 200 and the same response body as the first request.
    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()
