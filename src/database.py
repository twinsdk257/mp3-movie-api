import sqlite3
from pathlib import Path


def get_connection(db_path):
    """Return a fresh connection with rows accessible by column name."""
    # TODO: create the parent directory, connect, and set sqlite3.Row.
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    return connection

def initialize_database(db_path):
    """Create the movie table if it does not exist."""
    # TODO: create the movie table if needed, commit, and close the connection.
    connection = get_connection(db_path)

    try:
        connection.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    release_year INTEGER,
                    rating REAL,
                    genre TEXT
                )
            """)

        connection.commit()

    finally:
        connection.close()